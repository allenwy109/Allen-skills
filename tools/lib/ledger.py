#!/usr/bin/env python3
"""统一证据账的读写、合并、检查与渲染（设计 §3）。只用标准库。

证据账位于 <任务文件夹>/03_evidence/ledger/，每张表一个 JSONL 文件（一行一条记录），是唯一真源。
字段与枚举只在 tools/lib/schema/ledger.schema.json 里定义。

命令行（在仓库根目录或安装后的 _allen-runtime 下）：
  python3 tools/lib/ledger.py <任务文件夹> init
  python3 tools/lib/ledger.py <任务文件夹> check [--json]
  python3 tools/lib/ledger.py <任务文件夹> render
  python3 tools/lib/ledger.py <任务文件夹> merge <研究线>
  python3 tools/lib/ledger.py <任务文件夹> next-id <表> [--line M]
check 有错误时以 1 退出。

写入规则：
- 所有写入都先加锁（ledger/.lock），把原文件备份到 ledger/.backup/，写临时文件后原子替换。
- add 会校验整条记录；patch 只改给出的字段，未给出的字段保持原样，然后校验合并后的记录。
- 子代理不直接写证据账，而是写 ledger/staging/<研究线>/<表>.jsonl，由主线程 merge。
"""
import argparse
import contextlib
import fcntl
import json
import os
import pathlib
import re
import shutil
import sys
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from tools.lib import schema_check  # noqa: E402

KEEP_BACKUPS = 20
CONTROL_TYPES = {"control", "brand_of", "branch_of"}
CLAIM_CARD_TYPES = {"data", "fact", "opinion", "insight", "risk", "recommendation"}
DELIVERABLE_PLACEMENTS = {"chapter", "page", "speaker_notes", "backup", "appendix"}
UNREADABLE_ACCESS = {"metadata_only", "blocked", "unreadable"}
KIND_ATTRIBUTES = {"data": {"actual"}, "forecast": {"forecast"}, "third_party_view": {"opinion"}, "estimate": {"actual", "estimate"}}


class LedgerError(Exception):
    pass


def id_format(table, spec):
    """从 id_pattern 推出前缀和最少位数，例如 ^ev-[0-9]{4,}$ → ("ev-", 4)。"""
    m = re.match(r"^\^([A-Za-z]+-)\[0-9\]\{(\d+),\}\$$", spec["id_pattern"])
    if not m:
        raise LedgerError(f"表 {table} 的 id 不能自动编号")
    return m.group(1), int(m.group(2))


def iter_refs(spec, value):
    """遍历一个值里的所有引用，产出 (目标表, 引用的 id)。"""
    if value is None:
        return
    t = spec["type"]
    if "ref" in spec and isinstance(value, str):
        yield spec["ref"], value
    elif t == "array" and isinstance(value, list):
        for item in value:
            yield from iter_refs(spec["items"], item)
    elif t == "object" and isinstance(value, dict):
        for k, s in spec["fields"].items():
            yield from iter_refs(s, value.get(k))
    elif t == "map" and isinstance(value, dict):
        for v in value.values():
            yield from iter_refs(spec["values"], v)


def rewrite_refs(spec, value, mapping):
    """把值里引用的 id 按 mapping[表][旧 id] 替换，返回新值。"""
    if value is None:
        return None
    t = spec["type"]
    if "ref" in spec and isinstance(value, str):
        return mapping.get(spec["ref"], {}).get(value, value)
    if t == "array" and isinstance(value, list):
        return [rewrite_refs(spec["items"], v, mapping) for v in value]
    if t == "object" and isinstance(value, dict):
        return {k: rewrite_refs(spec["fields"].get(k, {"type": "string"}), v, mapping) for k, v in value.items()}
    if t == "map" and isinstance(value, dict):
        return {k: rewrite_refs(spec["values"], v, mapping) for k, v in value.items()}
    return value


def issue(level, table, rid, message):
    return {"level": level, "table": table, "id": rid, "message": message}


class Ledger:
    def __init__(self, task_dir, schema=None):
        self.task = pathlib.Path(task_dir)
        self.evidence_dir = self.task / "03_evidence"
        self.dir = self.evidence_dir / "ledger"
        self.schema = schema or schema_check.load("ledger.schema.json")

    # ---------- 基础读写 ----------
    def path(self, table):
        if table not in self.schema["tables"]:
            raise LedgerError(f"未知的表：{table}")
        return self.dir / self.schema["tables"][table]["file"]

    @staticmethod
    def _read_file(path):
        if not path.is_file():
            return []
        out = []
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if line.strip():
                try:
                    out.append(json.loads(line))
                except ValueError as err:
                    raise LedgerError(f"{path} 第 {n} 行不是合法 JSON：{err}")
        return out

    def read(self, table):
        return self._read_file(self.path(table))

    def get(self, table, rid):
        for r in self.read(table):
            if r.get("id") == rid:
                return r
        return None

    @contextlib.contextmanager
    def lock(self):
        self.dir.mkdir(parents=True, exist_ok=True)
        with open(self.dir / ".lock", "w") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)

    def _write(self, table, records):
        path = self.path(table)
        if path.is_file():
            backups = self.dir / ".backup"
            backups.mkdir(exist_ok=True)
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            shutil.copy2(path, backups / f"{path.stem}-{stamp}.jsonl")
            old = sorted(backups.glob(f"{path.stem}-*.jsonl"))
            for extra in old[:-KEEP_BACKUPS]:
                extra.unlink()
        tmp = path.with_suffix(".jsonl.tmp")
        tmp.write_text("".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in records), encoding="utf-8")
        os.replace(tmp, path)

    def _validate(self, table, record):
        errors = schema_check.check_record(self.schema, table, record)
        if errors:
            raise LedgerError("；".join(errors))

    # ---------- 编号 ----------
    def _next_id_from(self, table, existing_ids, line=None):
        if table == "sources":
            if not line or not re.match(r"^[ABD-Z]$", line):
                raise LedgerError("来源编号需要研究线字母（U、M、A、B……，不能用 C）")
            nums = [int(i[1:]) for i in existing_ids if re.match(rf"^{line}\d+$", i)]
            n = max(nums, default=0) + 1
            return f"{line}{n:03d}"
        if table == "project":
            return "project"
        prefix, width = id_format(table, self.schema["tables"][table])
        nums = [int(i[len(prefix):]) for i in existing_ids if i.startswith(prefix) and i[len(prefix):].isdigit()]
        return f"{prefix}{max(nums, default=0) + 1:0{width}d}"

    def next_id(self, table, line=None):
        return self._next_id_from(table, [r["id"] for r in self.read(table)], line)

    # ---------- 写入 ----------
    def add(self, table, record, line=None):
        with self.lock():
            records = self.read(table)
            record = dict(record)
            if not record.get("id"):
                record["id"] = self._next_id_from(table, [r["id"] for r in records], line)
            if any(r["id"] == record["id"] for r in records):
                raise LedgerError(f"{table} 里已有 {record['id']}")
            self._validate(table, record)
            records.append(record)
            self._write(table, records)
            return record["id"]

    def patch(self, table, rid, fields):
        if "id" in fields and fields["id"] != rid:
            raise LedgerError("patch 不能修改 id")
        with self.lock():
            records = self.read(table)
            for i, r in enumerate(records):
                if r["id"] == rid:
                    merged = {**r, **fields}
                    merged = {k: v for k, v in merged.items() if v is not None}
                    self._validate(table, merged)
                    records[i] = merged
                    self._write(table, records)
                    return merged
            raise LedgerError(f"{table} 里没有 {rid}")

    def init(self):
        self.dir.mkdir(parents=True, exist_ok=True)
        for sub in ("raw/sources", "raw/files", "raw/user", "data/extracted", "data/curated", "analysis", "notes", "search-logs"):
            (self.evidence_dir / sub).mkdir(parents=True, exist_ok=True)
        if not self.get("project", "project"):
            self.add("project", {"id": "project"})

    # ---------- 合并子代理暂存 ----------
    def merge(self, line):
        """把 staging/<line>/ 下的记录并入证据账。
        来源保留原 ID（研究线自带前缀）；其他表重新编号，并改写暂存记录之间的引用。
        同一 URL 且第一个原件哈希相同的来源，标为 duplicate_of 已有来源。"""
        staging = self.dir / "staging" / line
        if not staging.is_dir():
            raise LedgerError(f"没有暂存目录：{staging}")
        tables = self.schema["tables"]
        staged = None
        if (self.task / "consulting-project.json").is_file():
            metadata_path = self.task / "03r_research" / "tasks" / f"{line}.json"
            handoff_path = self.task / "research-handoffs" / f"{line}.json"
            try:
                metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
                handoff = json.loads(handoff_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise LedgerError(f"咨询项目研究线 {line} 缺少可核验的 accepted 元数据或 handoff：{exc}") from exc
            handoff_errors = schema_check.check_document(schema_check.load("research-handoff.schema.json"), handoff)
            if handoff_errors:
                raise LedgerError(f"咨询项目研究线 {line} handoff 不符合 schema：{'；'.join(handoff_errors)}")
            accepted = (
                isinstance(metadata, dict) and isinstance(handoff, dict)
                and metadata.get("code") == line and metadata.get("status") == "accepted"
                and handoff.get("line_id") == line and handoff.get("project_manager_disposition") == "accepted"
                and metadata.get("role") == handoff.get("role")
            )
            if not accepted:
                raise LedgerError(f"咨询项目研究线 {line} 未同时获得 accepted 元数据和 handoff，禁止合并")
            staged = {table: self._read_file(staging / spec["file"]) for table, spec in tables.items()}
            reviewed_claims = set(handoff["supported_claims"])
            bound_claims = {record["id"] for record in staged["claims"]}
            for table, records in staged.items():
                fields = tables[table]["fields"]
                for record in records:
                    for field, value in record.items():
                        if field in fields:
                            bound_claims.update(ref for target, ref in iter_refs(fields[field], value) if target == "claims")
            unreviewed = sorted(bound_claims - reviewed_claims)
            if unreviewed:
                raise LedgerError(f"咨询项目研究线 {line} 含 handoff.supported_claims 未明确接受的 claim：{'、'.join(unreviewed)}")
        with self.lock():
            current = {t: self.read(t) for t in tables}
            if staged is None:
                staged = {t: self._read_file(staging / spec["file"]) for t, spec in tables.items()}
            mapping = {}
            for t, recs in staged.items():
                if t in ("sources", "project") or not recs:
                    continue
                ids = [r["id"] for r in current[t]]
                mapping[t] = {}
                for r in recs:
                    new = self._next_id_from(t, ids)
                    mapping[t][r["id"]] = new
                    ids.append(new)
            known = {}
            for s in current["sources"]:
                files = s.get("original_files") or []
                if s.get("url") and files and not s.get("duplicate_of"):
                    known[(s["url"], files[0]["sha256"])] = s["id"]
            for t, recs in staged.items():
                if not recs:
                    continue
                spec = tables[t]
                for r in recs:
                    new = {k: rewrite_refs(spec["fields"][k], v, mapping) if k in spec["fields"] else v for k, v in r.items()}
                    new["id"] = mapping.get(t, {}).get(r["id"], r["id"])
                    if t == "sources":
                        if any(s["id"] == new["id"] for s in current["sources"]):
                            raise LedgerError(f"来源 {new['id']} 已存在，研究线 {line} 不能复用来源 ID")
                        files = new.get("original_files") or []
                        key = (new.get("url"), files[0]["sha256"]) if new.get("url") and files else None
                        if key and key in known:
                            new["duplicate_of"] = known[key]
                        elif key:
                            known[key] = new["id"]
                    self._validate(t, new)
                    current[t].append(new)
            for t, recs in staged.items():
                if recs:
                    self._write(t, current[t])
            shutil.rmtree(staging)
            return {t: len(r) for t, r in staged.items() if r}

    # ---------- 检查 ----------
    def check(self):
        issues = []
        tables = self.schema["tables"]
        data = {}
        for t in tables:
            try:
                data[t] = self.read(t)
            except LedgerError as err:
                issues.append(issue("error", t, None, str(err)))
                data[t] = []
        index = {t: {r.get("id"): r for r in recs} for t, recs in data.items()}
        for t, recs in data.items():
            seen = set()
            for r in recs:
                rid = r.get("id")
                for e in schema_check.check_record(self.schema, t, r):
                    issues.append(issue("error", t, rid, e))
                if rid in seen:
                    issues.append(issue("error", t, rid, "id 重复"))
                seen.add(rid)
                for k, spec in tables[t]["fields"].items():
                    for target, ref in iter_refs(spec, r.get(k)):
                        if ref not in index[target]:
                            issues.append(issue("error", t, rid, f"{k} 引用了不存在的 {target}:{ref}"))
        issues += self._semantic_checks(data, index)
        return issues

    def _semantic_checks(self, data, index):
        out = []
        project = index["project"].get("project", {})
        links_by_claim = {}
        for ce in data["claim_evidence"]:
            links_by_claim.setdefault(ce.get("claim_id"), []).append(ce)
        conflicted = {cid for x in data["conflicts"] for cid in x.get("claim_ids") or []}

        for c in data["claims"]:
            cid = c.get("id")
            if c.get("materiality") in ("critical", "major") and c.get("affects_conclusion") is False:
                out.append(issue("error", "claims", cid, "关键或重要的主张必须 affects_conclusion=true"))
            links = links_by_claim.get(cid, [])
            allowed = KIND_ATTRIBUTES.get(c.get("kind"))
            for ce in links:
                ev = index["evidence"].get(ce.get("evidence_id"))
                if not ev:
                    continue
                src = index["sources"].get(ev.get("source_id"), {})
                if ce.get("relation") == "supports" and allowed and ev.get("attribute") not in allowed:
                    out.append(issue("error", "claims", cid, f"kind={c.get('kind')} 的主张不能由 attribute={ev.get('attribute')} 的证据 {ev['id']} 支持"))
                if ce.get("relation") in ("supports", "contradicts") and src.get("access") in UNREADABLE_ACCESS:
                    out.append(issue("error", "claims", cid, f"证据 {ev['id']} 的来源 {src.get('id')} 无法读取（{src.get('access')}），不能形成证据"))
                if ce.get("relation") in ("supports", "contradicts") and project.get("historical") and src.get("time_scope") == "retrospective":
                    out.append(issue("error", "claims", cid, f"历史时点研究不能用事后资料 {src.get('id')} 支持或反驳结论"))
                if (ce.get("relation") == "supports" and ev.get("entity_id") and c.get("entity_id")
                        and ev["entity_id"] != c["entity_id"]):
                    if not ce.get("bridge") or c.get("kind") != "estimate":
                        out.append(issue("error", "claims", cid, f"用 {ev['entity_id']} 的证据支持 {c['entity_id']} 的主张，必须写 bridge 且主张 kind=estimate"))
            if c.get("verification") == "refuted" and not any(ce.get("relation") == "contradicts" for ce in links):
                out.append(issue("error", "claims", cid, "已推翻的主张必须至少有一条 contradicts 证据"))
            if c.get("verification") == "conflicting" and cid not in conflicted:
                out.append(issue("error", "claims", cid, "有冲突的主张必须在 conflicts 表里登记"))

        for card in data["cards"]:
            kid, tier = card.get("id"), card.get("value_tier")
            claim = index["claims"].get(card.get("claim_id"))
            if tier in ("A", "B") and card.get("type") in CLAIM_CARD_TYPES and not card.get("claim_id"):
                out.append(issue("error", "cards", kid, "A/B 级的数据、事实、观点、洞察、风险、建议类卡片必须关联主张"))
            if not card.get("claim_id") and (not card.get("nature") or not card.get("confidence") or not card.get("confidence_reason")):
                out.append(issue("warning", "cards", kid, "没有关联主张的卡片应填写性质、可信度及依据"))
            if tier in ("A", "B") and schema_check.empty(card.get("meaning")):
                out.append(issue("error", "cards", kid, "A/B 级卡片必须填写含义"))
            if tier == "A" and claim and claim.get("affects_conclusion") is False:
                out.append(issue("error", "cards", kid, f"A 级卡片关联的主张 {claim['id']} 必须 affects_conclusion=true"))
            places = {p.get("where") for p in card.get("placement") or []}
            if tier == "A" and "not_used" in places:
                out.append(issue("error", "cards", kid, "A 级卡片不能“确认不用”：要么写依据降级，要么承认主线有缺陷"))
            if tier == "C" and places & DELIVERABLE_PLACEMENTS:
                out.append(issue("error", "cards", kid, "C 级卡片不能进入交付物"))

        out += self._metric_checks(data["metrics"], index["metrics"])

        for rel in data["relations"]:
            if rel.get("parent_id") == rel.get("child_id"):
                out.append(issue("error", "relations", rel.get("id"), "不能自己控制自己"))
            if rel.get("effective_to") and rel.get("effective_from") and rel["effective_to"] <= rel["effective_from"]:
                out.append(issue("error", "relations", rel.get("id"), "生效区间为左闭右开，effective_to 必须晚于 effective_from"))
        control = set(CONTROL_TYPES)
        if project.get("joint_control_triggers"):
            control.add("joint_control")
        edges = [(r["parent_id"], r["child_id"]) for r in data["relations"]
                 if r.get("relation_type") in control and r.get("state") == "current" and r.get("verification") == "verified"]
        if has_cycle(edges):
            out.append(issue("error", "relations", None, "现行且已核实的控制关系存在环"))

        for kind in ("discovered", "fulltext", "read"):
            for cov in data["coverage"]:
                for rr_id in cov.get(f"latest_{kind}_ids") or []:
                    rr = index["research_reports"].get(rr_id)
                    if rr and cov["id"] not in (rr.get(f"latest_{kind}_for") or []):
                        out.append(issue("error", "coverage", cov["id"], f"latest_{kind}_ids 指向 {rr_id}，但对方的 latest_{kind}_for 没有反向登记"))
            for rr in data["research_reports"]:
                for cov_id in rr.get(f"latest_{kind}_for") or []:
                    cov = index["coverage"].get(cov_id)
                    if cov and rr["id"] not in (cov.get(f"latest_{kind}_ids") or []):
                        out.append(issue("error", "research_reports", rr["id"], f"latest_{kind}_for 指向 {cov_id}，但对方的 latest_{kind}_ids 没有登记"))

        for t, a, b in (("evidence", "period_start", "period_end"), ("search_log", "period_start", "period_end"),
                        ("entities", "listing_start", "listing_end"), ("sources", "published", "revised_date")):
            for r in data[t]:
                if r.get(a) and r.get(b) and r[a] > r[b]:
                    out.append(issue("error", t, r.get("id"), f"{a} 不能晚于 {b}"))
        for s in data["sources"]:
            for k in ("supersedes", "duplicate_of", "upstream_source_id"):
                if s.get(k) and s.get(k) == s.get("id"):
                    out.append(issue("error", "sources", s["id"], f"{k} 不能指向自己"))
        out += self._snapshot_checks(data["sources"])
        return out

    def _snapshot_checks(self, sources):
        """采集元数据以快照头为真源（设计 §3.2）：sources 表的同名字段必须与快照头一致。"""
        from tools.lib import snapshot
        out = []
        for s in sources:
            if not s.get("snapshot"):
                continue
            try:
                meta, _ = snapshot.read(self.evidence_dir / s["snapshot"])
            except (OSError, UnicodeError, snapshot.SnapshotError) as e:
                out.append(issue("error", "sources", s["id"], f"快照无法读取：{e}"))
                continue
            for k in snapshot.fields():
                if meta.get(k) != s.get(k) and not (meta.get(k) in (None, []) and s.get(k) in (None, [])):
                    out.append(issue("error", "sources", s["id"], f"{k} 与快照头不一致（快照是真源，改证据账去对齐）"))
        return out

    @staticmethod
    def _metric_checks(metrics, index):
        out = []
        edges = []
        for m in metrics:
            mid = m.get("id")
            has_value, has_formula = m.get("value") is not None, m.get("formula") is not None
            if has_value and has_formula:
                out.append(issue("error", "metrics", mid, "value 和 formula 只能二选一"))
            if m.get("status") == "present" and not (has_value or has_formula):
                out.append(issue("error", "metrics", mid, "有值的指标必须有 value 或 formula"))
            if m.get("status") == "missing" and has_value:
                out.append(issue("error", "metrics", mid, "缺失的指标不能填值（缺失不是 0）"))
            for arg in (m.get("formula") or {}).get("args") or []:
                edges.append((mid, arg))
                if arg == mid:
                    out.append(issue("error", "metrics", mid, "公式不能引用自己"))
        if has_cycle(edges):
            out.append(issue("error", "metrics", None, "指标公式存在循环引用"))
        return out

    # ---------- 渲染 ----------
    def render(self):
        """生成可读版：03_evidence/ledger.md、notes/<研究线>.md、search-logs/<研究线>.md。"""
        enums = self.schema["enums"]

        def label(enum, v):
            return enums[enum]["labels"].get(v, v) if v else "—"

        counts = {t: len(self.read(t)) for t in self.schema["tables"] if t != "project"}
        claims, gaps, conflicts = self.read("claims"), self.read("gaps"), self.read("conflicts")
        lines = ["# 证据账（由 ledger.py render 生成，不要手改）", "", "## 记录数", "", "| 表 | 条数 |", "|---|---|"]
        lines += [f"| {t} | {n} |" for t, n in counts.items()]
        lines += ["", "## 主张", "", "| ID | 身份 | 核实状态 | 影响结论 | 主张 |", "|---|---|---|---|---|"]
        lines += [f"| {c['id']} | {label('claim_kind', c.get('kind'))} | {label('verification', c.get('verification'))} | {'是' if c.get('affects_conclusion') else '否'} | {c.get('statement', '')} |" for c in claims]
        open_gaps = [g for g in gaps if g.get("status") not in ("resolved", "unavailable")]
        lines += ["", "## 未关闭的缺口", "", "| ID | 优先级 | 路由 | 描述 |", "|---|---|---|---|"]
        lines += [f"| {g['id']} | {g.get('priority', '')} | {label('gap_route', g.get('route'))} | {g.get('description', '')} |" for g in open_gaps]
        open_x = [x for x in conflicts if x.get("status") == "open"]
        lines += ["", "## 未处理的冲突", "", "| ID | 改变决策 | 分析 |", "|---|---|---|"]
        lines += [f"| {x['id']} | {'是' if x.get('decision_changing') else '否'} | {x.get('analysis', '')} |" for x in open_x]
        self.evidence_dir.mkdir(parents=True, exist_ok=True)
        (self.evidence_dir / "ledger.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

        notes_dir = self.evidence_dir / "notes"
        notes_dir.mkdir(exist_ok=True)
        for old in notes_dir.glob("*.md"):
            old.unlink()
        by_line = {}
        for ev in self.read("evidence"):
            by_line.setdefault(ev.get("research_line") or "M", []).append(ev)
        for line, evs in sorted(by_line.items()):
            out = [f"# 研究线 {line} 的证据块（由 ledger.py render 生成，不要手改）", ""]
            for ev in evs:
                title = ev.get("claim_text") or ev["excerpt"][:20]
                out += [f"## {ev['id']} {title}", f"- 论断: {ev.get('claim_text') or '—'}",
                        f"- 来源: `{ev['source_id']}` · 定位: {ev['locator']}", "- 逐字摘录:"]
                out += [f"  > {seg}" for seg in ev["excerpt"].splitlines()]
                out += [f"- 解读: {ev.get('interpretation') or '—'}", f"- 贴合度: {label('fit', ev.get('fit'))}",
                        f"- 用于: {'、'.join(ev.get('used_in') or []) or 'none'}",
                        f"- 交叉来源: {'、'.join(ev.get('cross_sources') or []) or 'none'}", ""]
            (notes_dir / f"{line}.md").write_text("\n".join(out), encoding="utf-8")

        logs_dir = self.evidence_dir / "search-logs"
        logs_dir.mkdir(exist_ok=True)
        for old in logs_dir.glob("*.md"):
            old.unlink()
        by_line = {}
        for q in self.read("search_log"):
            by_line.setdefault(q["research_line"], []).append(q)
        for line, qs in sorted(by_line.items()):
            out = [f"# 研究线 {line} 的检索日志（由 ledger.py render 生成，不要手改）", ""]
            for q in sorted(qs, key=lambda x: x["searched_at"]):
                discarded = "；".join(f"{d['target']}（{label('discard_reason', d['reason'])}）" for d in q.get("discarded") or []) or "无"
                out += [f"## {q['searched_at']} · {q['tool']}", f"- 查询原文: `{q['query']}`",
                        f"- 过滤: {q.get('filters') or '无'}", f"- 结果: {label('search_status', q['status'])}；看过：{q.get('results_seen') or '—'}",
                        f"- 打开并存档: {'、'.join(q.get('opened_source_ids') or []) or '无'}", f"- 弃用: {discarded}", ""]
            (logs_dir / f"{line}.md").write_text("\n".join(out), encoding="utf-8")


def has_cycle(edges):
    """有向图是否有环（Kahn 拓扑消去，避免递归过深）。"""
    nodes = {n for e in edges for n in e}
    indeg = {n: 0 for n in nodes}
    out = {n: [] for n in nodes}
    for a, b in edges:
        out[a].append(b)
        indeg[b] += 1
    queue = [n for n in nodes if indeg[n] == 0]
    seen = 0
    while queue:
        n = queue.pop()
        seen += 1
        for m in out[n]:
            indeg[m] -= 1
            if indeg[m] == 0:
                queue.append(m)
    return seen != len(nodes)


def main(argv=None):
    ap = argparse.ArgumentParser(description="统一证据账")
    ap.add_argument("task", help="任务文件夹")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init")
    c = sub.add_parser("check")
    c.add_argument("--json", action="store_true")
    sub.add_parser("render")
    m = sub.add_parser("merge")
    m.add_argument("line")
    n = sub.add_parser("next-id")
    n.add_argument("table")
    n.add_argument("--line")
    a = ap.parse_args(argv)
    led = Ledger(a.task)
    try:
        if a.cmd == "init":
            led.init()
            print(f"已初始化证据账：{led.dir}")
        elif a.cmd == "check":
            issues = led.check()
            errors = [i for i in issues if i["level"] == "error"]
            if a.json:
                print(json.dumps({"errors": len(errors), "issues": issues}, ensure_ascii=False, indent=1))
            else:
                for i in issues:
                    print(f"{'错误' if i['level'] == 'error' else '警告'}：{i['table']}:{i['id'] or '-'}：{i['message']}")
                print(f"证据账检查：错误 {len(errors)} 个，警告 {len(issues) - len(errors)} 个")
            return 1 if errors else 0
        elif a.cmd == "render":
            led.render()
            print(f"已生成 {led.evidence_dir / 'ledger.md'}、notes/、search-logs/")
        elif a.cmd == "merge":
            print(json.dumps(led.merge(a.line), ensure_ascii=False))
        elif a.cmd == "next-id":
            print(led.next_id(a.table, a.line))
    except LedgerError as err:
        print(f"错误：{err}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
