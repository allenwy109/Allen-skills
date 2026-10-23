"""研究检查（research check，设计 §5.1；能力清单 D2 与 H 节优化 4、5、7、8、10）。只用标准库，不执行包内任何脚本。

两种输入，同一套规则：
- 任务文件夹：读证据账（sources、evidence、search_log、project、reviews）、03_evidence/raw、03_evidence/data、
  03_evidence/analysis 和 03r_research/（brief、plan、report）。路径基准是 03_evidence/。
- 研究包（封包产物，上游 v2 布局）：读 package.json、raw/、sources.md、notes/、work/search-logs/、data/、analysis/、
  report.md、README.md、qa/。路径基准是包根。
- 轻量包（--profile lite）：raw/ + answer.md。

两种输入都先归一成同一个模型（快照、索引、证据摘录、检索日志、数据表、报告），再跑同一组检查。
"""
import csv
import datetime
import hashlib
import io
import json
import pathlib
import re
from decimal import Decimal, InvalidOperation

from tools.lib import schema_check, snapshot
from tools.lib.ledger import Ledger

SCHEMA = schema_check.load("ledger.schema.json")
ENUM = {k: SCHEMA["enums"][k]["values"] for k in ("tier", "grade", "capture_method", "access", "data_status", "search_applicability")}
LABEL = {k: SCHEMA["enums"][k]["labels"] for k in ("tier", "grade", "capture_method", "access")}
SOURCE_ID = re.compile(r"^[ABD-Z]\d{3,4}$")
DIGEST_EXCLUDE = {"README.md", "qa/review.json", "qa/checks.json", "manifest-sha256.txt"}
PACKAGE_KEYS = ("package_id", "topic", "information_cutoff", "data_status", "data_reason", "search_status", "search_reason")
PACKAGE_REQUIRED = ("report.md", "sources.md", "README.md", "work/brief.md", "work/plan.md")
TASK_REQUIRED = ("03r_research/brief.md", "03r_research/plan.md", "03r_research/report.md")
LEGACY = ("brief.md", "plan.md", "tasks", "raw/search-logs")
# 研究包快照头：任务文件夹快照字段 + 评价字段（封包时由证据账补齐）；supersedes、archive_url 可以为空
PACKAGE_META = ("id", "title", "url", "final_url", "author_org", "published", "accessed", "language", "tier", "grade",
                "conflict_of_interest", "capture_method", "access", "original_files", "research_line", "subquestions",
                "supersedes", "archive_url", "access_note", "rights_note")
NULLABLE = {"supersedes", "archive_url"}
TASK_META = ("id", "title", "accessed", "capture_method", "access", "original_files")   # 其余评价字段在证据账里，由 schema 校验
INDEX_COLUMNS = ("ID", "标题", "作者/机构", "发布", "访问", "层级", "可信度", "完整度", "采集方式", "本地文件", "URL", "引用号", "备注")
COMMON = ("record_id", "value", "value_type", "value_origin", "status", "source_id", "source_locator", "original_value", "input_ids", "method")
NUMERIC_CONTEXT = ("entity", "metric", "unit", "period", "geography", "scope")
DICT_COLS = ("dataset_id", "field", "type", "description", "unit", "missing_rule")
STATS_KEYS = ("snapshot_files", "snapshots_parsed", "notes_files", "note_blocks", "quotes_checked", "search_queries", "datasets",
              "data_records", "derived_records", "report_data_links")
STATS_START, STATS_END = "<!-- package-stats:start -->", "<!-- package-stats:end -->"
FILE_LIMIT, PACKAGE_LIMIT = 50 * 1024 * 1024, 500 * 1024 * 1024


class Result:
    def __init__(self):
        self.errors, self.warnings, self.stats = [], [], {}

    def e(self, msg):
        self.errors.append(msg)

    def w(self, msg):
        self.warnings.append(msg)


# ---------- 公共工具 ----------

def sha(path):
    return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()


def all_files(root, exclude=()):
    root = pathlib.Path(root)
    return sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file() and p.relative_to(root).as_posix() not in exclude)


def digest(root):
    """内容指纹：除 README、review、checks、manifest 外的所有文件，按路径排序生成「sha  路径」行，整体取 SHA-256。"""
    lines = [f"{sha(pathlib.Path(root) / p)}  {p}" for p in all_files(root, DIGEST_EXCLUDE)]
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


def symlinks(root):
    return [p for p in pathlib.Path(root).rglob("*") if p.is_symlink()]


def safe_path(base, value):
    """路径字段：非空、相对、不含 .. 和反斜杠、解析后在基准目录内、文件存在。返回 Path 或 None。"""
    if not isinstance(value, str) or not value or value.startswith("/") or "\\" in value or ".." in pathlib.PurePosixPath(value).parts:
        return None
    p = (pathlib.Path(base) / value).resolve()
    try:
        p.relative_to(pathlib.Path(base).resolve())
    except ValueError:
        return None
    return p if p.is_file() else None


def read_csv(path, res, where):
    try:
        text = pathlib.Path(path).read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError) as e:
        res.e(f"{where}：无法读取（{e}）")
        return None, []
    rows = list(csv.reader(io.StringIO(text)))
    if not rows or not any(rows[0]):
        res.e(f"{where}：没有表头")
        return None, []
    header = rows[0]
    if len(set(header)) != len(header) or any(not h for h in header):
        res.e(f"{where}：表头有空列名或重复列名")
        return None, []
    out = []
    for n, row in enumerate(rows[1:], 2):
        if len(row) != len(header):
            res.e(f"{where} 第 {n} 行：列数与表头不一致，整表不予采信")
            return header, []
        out.append(dict(zip(header, row)))
    return header, out


def normalize(text):
    """摘录比对用的归一化：去掉标题和引用符号、Markdown 链接只留文字、去掉强调符号、中文标点换半角、压空白、忽略大小写。"""
    text = re.sub(r"(?m)^ {0,3}[#>]+ ?", "", text)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"[`*_~]", "", text)
    text = text.translate(str.maketrans("“”‘’，。：（）；！？", "\"\"'',.:();!?"))
    return re.sub(r"\s+", " ", text).strip().casefold()


def quote_matches(excerpt, body):
    """摘录按 [...] 切成片段，片段必须按原顺序出现在快照正文里。返回 (片段数, 是否匹配)。"""
    parts = [normalize(p) for p in re.split(r"\[\s*(?:\.\.\.|…)\s*\]", excerpt)]
    parts = [p for p in parts if p]
    hay, pos = normalize(body), 0
    for p in parts:
        i = hay.find(p, pos)
        if i < 0:
            return len(parts), False
        pos = i + len(p)
    return len(parts), bool(parts)


def body_empty(body):
    return not body.strip() or body.strip() == snapshot.EMPTY_BODY.strip()


# ---------- 读取：归一成同一个模型 ----------

class Model:
    def __init__(self, kind, root, base):
        self.kind, self.root, self.base = kind, pathlib.Path(root), pathlib.Path(base)
        self.project, self.snapshots, self.index, self.evidence, self.logs = {}, {}, {}, [], []
        self.report_path, self.claims, self.ledger_sources, self.links = None, [], {}, []


def load_task(task, res):
    m = Model("task", task, pathlib.Path(task) / "03_evidence")
    led = Ledger(task)
    for i in led.check():
        if i["level"] == "error":
            res.e(f"证据账 {i['table']}:{i['id']}：{i['message']}")
    proj = (led.read("project") or [{}])[0]
    m.project = {k: proj.get(k) for k in ("data_status", "data_reason", "search_status", "search_reason")}
    m.ledger_sources = {s["id"]: s for s in led.read("sources")}
    m.index = {sid: {"kind": "ledger", **s} for sid, s in m.ledger_sources.items()}
    m.evidence = [{"where": f"evidence {e['id']}", "source": e["source_id"], "locator": e.get("locator"), "excerpt": e.get("excerpt") or ""}
                  for e in led.read("evidence")]
    m.logs = [{"where": f"search_log {q['id']}", "at": q.get("searched_at"), "tool": q.get("tool"), "query": q.get("query"),
               "opened": q.get("opened_source_ids") or [], "discarded": q.get("discarded") or [], "has_discard_reason": True}
              for q in led.read("search_log")]
    m.claims = led.read("claims")
    m.claim_links = led.read("claim_evidence")
    m.evidence_rows = {e["id"]: e for e in led.read("evidence")}
    m.reviews = led.read("reviews")
    m.report_path = pathlib.Path(task) / "03r_research" / "report.md"
    return m


def load_package(root, res):
    m = Model("package", root, root)
    root = pathlib.Path(root)
    pj = root / "package.json"
    if not pj.is_file():
        res.e("没有 package.json：只读诊断为 legacy 包，不迁移、不封包")
        m.legacy = True
        return m
    m.legacy = False
    try:
        doc = json.loads(pj.read_text(encoding="utf-8-sig"))
    except ValueError as e:
        res.e(f"package.json 解析失败：{e}")
        doc = {}
    if not isinstance(doc, dict):
        res.e("package.json 顶层不是对象")
        doc = {}
    if type(doc.get("schema_version")) is not int or doc.get("schema_version") != 2:
        res.e("package.json 的 schema_version 必须是整数 2")
    for k in PACKAGE_KEYS:
        if not isinstance(doc.get(k), str) or not doc.get(k).strip():
            res.e(f"package.json 的 {k} 必须是非空字符串")
    m.package = doc
    m.project = {k: doc.get(k) for k in ("data_status", "data_reason", "search_status", "search_reason")}
    for old in LEGACY:
        if (root / old).exists():
            res.e(f"研究包里混有旧布局：{old}")
    sm = root / "sources.md"
    if sm.is_file():
        m.index = parse_index(sm.read_text(encoding="utf-8-sig"), res)
    notes = root / "notes"
    res.stats["notes_files"] = 0
    if notes.is_dir():
        for f in sorted(notes.rglob("*")):
            if f.is_file() and f.suffix != ".md":
                res.e(f"notes 下只允许 .md：{f.relative_to(root)}")
            elif f.is_file():
                res.stats["notes_files"] += 1
                m.evidence += parse_notes(f.read_text(encoding="utf-8-sig"), f.relative_to(root).as_posix(), res)
    logs = root / "work" / "search-logs"
    if logs.is_dir():
        for f in sorted(logs.rglob("*")):
            if f.is_file() and f.suffix != ".md":
                res.e(f"检索日志目录只允许 .md：{f.relative_to(root)}")
            elif f.is_file():
                m.logs += parse_logs(f.read_text(encoding="utf-8-sig"), f.relative_to(root).as_posix(), res)
    m.report_path = root / "report.md"
    return m


def parse_index(text, res):
    """sources.md：按表头名解析（列顺序变了也不误报）。"""
    rows, header = {}, None
    for line in text.splitlines():
        if not line.strip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if header is None:
            if "ID" in cells:
                header = cells
                missing = [c for c in INDEX_COLUMNS if c not in header]
                if missing:
                    res.e(f"sources.md 表头缺少列：{'、'.join(missing)}")
            continue
        if set("".join(cells)) <= set("-: "):
            continue
        row = dict(zip(header, cells))
        sid = row.get("ID", "")
        if not SOURCE_ID.match(sid):
            continue
        if len(cells) < len(header):
            res.e(f"sources.md 中 {sid} 这一行列数不足")
        if sid in rows:
            res.e(f"sources.md 中来源 ID 重复：{sid}")
        rows[sid] = {"kind": "md", **row}
    return rows


EVIDENCE_HEAD = re.compile(r"^## (\S+)")


def parse_notes(text, where, res):
    blocks, cur = [], None
    for line in text.splitlines() + ["## END"]:
        if line.startswith("## "):
            if cur:
                blocks.append(cur)
            cur = {"title": line[3:].strip(), "lines": []} if line != "## END" else None
        elif cur is not None:
            cur["lines"].append(line)
    if not blocks:
        res.e(f"{where}：没有任何 ## 证据块")
    out = []
    for b in blocks:
        src = [l for l in b["lines"] if l.startswith("- 来源:")]
        quote_heads = [i for i, l in enumerate(b["lines"]) if l.startswith("- 逐字摘录:")]
        m = re.match(r"- 来源: `([^`]+)` · 定位: (.+)$", src[0]) if len(src) == 1 else None
        if not m or len(quote_heads) != 1:
            res.e(f"{where}「{b['title']}」：证据块无法解析（要恰有一组「- 来源: `ID` · 定位: …」和「- 逐字摘录:」）")
            continue
        quote = []
        for l in b["lines"][quote_heads[0] + 1:]:
            if re.match(r"^\s+>", l):
                quote.append(re.sub(r"^\s+> ?", "", l))
            elif l.startswith("- "):
                break
        out.append({"where": f"{where}「{b['title']}」", "source": m.group(1), "locator": m.group(2).strip(), "excerpt": "\n".join(quote)})
    return out


def parse_logs(text, where, res):
    out, cur = [], None
    for line in text.splitlines() + ["## END"]:
        if line.startswith("## "):
            if cur:
                out.append(cur)
            if line == "## END":
                break
            head = line[3:].split(" · ", 1)
            cur = {"where": f"{where}「{line[3:]}」", "at": head[0].strip(), "tool": head[1].strip() if len(head) > 1 else "", "query": None,
                   "opened": [], "discarded": [], "has_discard_reason": True}
        elif cur is not None:
            if line.startswith("- 查询原文:"):
                q = re.search(r"`([^`]+)`", line)
                cur["query"] = q.group(1).strip() if q else None
            elif line.startswith("- 打开并存档:"):
                cur["opened"] = [x for x in re.findall(r"[ABD-Z]\d{3,4}", line)]
            elif line.startswith("- 弃用:"):
                items = [x.strip() for x in re.split(r"[；;]", line.split(":", 1)[1]) if x.strip() and x.strip() not in ("无", "none")]
                cur["discarded"] = items
                cur["has_discard_reason"] = all("（" in x or "(" in x for x in items)
    if not out:
        res.e(f"{where}：没有任何 ## 检索块")
    return out


# ---------- 检查 ----------

def check_sources(m, res, lite=False):
    base = m.base
    sdir = base / "raw" / "sources"
    files = sorted(sdir.rglob("*")) if sdir.is_dir() else []
    res.stats["snapshot_files"] = sum(1 for f in files if f.is_file())
    parsed = {}
    for f in files:
        if not f.is_file():
            continue
        rel = f.relative_to(base).as_posix()
        if f.suffix != ".md" or f.parent != sdir:
            res.e(f"raw/sources 只允许一级 .md 文件：{rel}")
            continue
        try:
            meta, body = snapshot.read(f)
        except (snapshot.SnapshotError, UnicodeError) as e:
            res.e(f"快照无法解析：{e}")
            continue
        sid = meta.get("id")
        if not isinstance(sid, str) or not SOURCE_ID.match(sid):
            res.e(f"{rel}：来源 ID 无效（{sid}）")
            continue
        if sid in parsed:
            res.e(f"来源 ID 重复：{sid}")
            continue
        if f.name.split("-", 1)[0] != sid:
            res.e(f"{rel}：文件名前缀与 ID {sid} 不一致")
        if m.kind == "task" and sid in m.ledger_sources:      # 快照头与证据账是否一致由 ledger check 负责（已并入本检查的错误）
            meta = {**{k: m.ledger_sources[sid].get(k) for k in PACKAGE_META}, **meta}
        required = PACKAGE_META if m.kind == "package" else TASK_META
        for k in required:
            v = meta.get(k)
            if k in NULLABLE or k == "subquestions":
                continue
            if k in ("url", "final_url") and str(meta.get("id", "")).startswith("U"):
                continue
            if v is None or v == "" or (k != "original_files" and v == []):
                res.e(f"{sid}：缺少元数据字段 {k}")
        for k in ("tier", "grade", "capture_method", "access"):
            if meta.get(k) is not None and meta.get(k) not in ENUM[k]:
                res.e(f"{sid}：{k}={meta.get(k)} 不在枚举里")
        orig = meta.get("original_files")
        if not isinstance(orig, list) or not all(isinstance(o, dict) and isinstance(o.get("path"), str) for o in orig):
            res.e(f"{sid}：original_files 必须是 {{path, sha256}} 列表")
            orig = []
        for o in orig:
            p = safe_path(base, o["path"])
            if p is None:
                res.e(f"{sid}：原件路径非法或文件不存在：{o['path']}")
            elif not re.fullmatch(r"[0-9a-f]{64}", str(o.get("sha256"))):
                res.e(f"{sid}：原件 {o['path']} 的 sha256 不是 64 位十六进制")
            elif sha(p) != o["sha256"]:
                res.e(f"{sid}：原件 {o['path']} 的哈希与登记不一致（原件被改动）")
            elif p.stat().st_size > FILE_LIMIT:
                res.w(f"{sid}：原件 {o['path']} 超过 50MB")
        if meta.get("access") in ("full", "partial") and body_empty(body):
            res.e(f"{sid}：完整度为 {meta.get('access')}，但快照正文为空")
        parsed[sid] = {"path": rel, "meta": meta, "body": body}
    res.stats["snapshots_parsed"] = len(parsed)
    res.stats["access"] = {k: sum(1 for s in parsed.values() if s["meta"].get("access") == k) for k in ENUM["access"]}
    m.snapshots = parsed
    if not parsed:
        res.e("一个快照都没有（覆盖为 0）")
    registered = {o["path"] for s in parsed.values() for o in s["meta"].get("original_files") or [] if isinstance(o, dict)}
    for sub in ("raw/files", "raw/user", "raw/user-provided"):
        d = base / sub
        if d.is_dir():
            for f in sorted(d.rglob("*")):
                if f.is_file() and f.relative_to(base).as_posix() not in registered:
                    res.e(f"原件没有被任何快照登记：{f.relative_to(base).as_posix()}")
    if lite:
        return
    for sid in sorted(set(parsed) - set(m.index)):
        res.e(f"快照 {sid} 没有登记在来源索引里")
    for sid in sorted(set(m.index) - set(parsed)):
        if m.index[sid].get("kind") == "md" or m.index[sid].get("snapshot"):
            res.e(f"来源索引里的 {sid} 没有可解析的快照")
    for sid, row in m.index.items():
        if row.get("kind") != "md" or sid not in parsed:
            continue
        meta = parsed[sid]["meta"]
        expect = {"完整度": LABEL["access"].get(meta.get("access")), "采集方式": LABEL["capture_method"].get(meta.get("capture_method")),
                  "层级": LABEL["tier"].get(meta.get("tier")), "可信度": meta.get("grade"), "标题": meta.get("title")}
        for col, value in expect.items():
            if col in row and value is not None and row[col] != value:
                res.e(f"sources.md 中 {sid} 的「{col}」与快照不一致（{row[col]} ≠ {value}）")
        if parsed[sid]["path"] not in row.get("本地文件", ""):
            res.e(f"sources.md 中 {sid} 的「本地文件」没有快照路径 {parsed[sid]['path']}")


def check_evidence(m, res):
    blocks = quotes = 0
    for ev in m.evidence:
        blocks += 1
        snap = m.snapshots.get(ev["source"])
        if snap is None:
            res.e(f"{ev['where']}：引用的来源 {ev['source']} 没有快照")
            continue
        if not ev.get("locator"):
            res.e(f"{ev['where']}：缺少定位")
        n, ok = quote_matches(ev["excerpt"], snap["body"])
        if n == 0:
            res.e(f"{ev['where']}：摘录为空")
        elif not ok:
            res.e(f"{ev['where']}：摘录在 {ev['source']} 的快照正文里找不到（片段要按原顺序逐字出现；不能凭记忆改写）")
        else:
            quotes += 1
    res.stats["note_blocks"], res.stats["quotes_checked"] = blocks, quotes
    if quotes == 0:
        res.e("没有任何可核对的摘录（覆盖为 0，不能声称已核验）")


def check_logs(m, res):
    queries = sum(1 for q in m.logs if q.get("query"))
    for q in m.logs:
        if not q.get("query"):
            res.e(f"{q['where']}：缺少「查询原文」")
        if q.get("at") and not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2})?([+-]\d{2}:\d{2}|Z)", str(q["at"])):
            res.w(f"{q['where']}：检索时间不是带时区的 ISO 格式")
        if not q.get("tool"):
            res.w(f"{q['where']}：没有写检索工具")
        if not q.get("has_discard_reason", True):
            res.w(f"{q['where']}：弃用条目没有写原因")
        for sid in q.get("opened") or []:
            if sid not in m.snapshots:
                res.w(f"{q['where']}：「打开并存档」里的 {sid} 没有快照")
    res.stats["search_files"], res.stats["search_queries"] = len({q["where"].split("「")[0] for q in m.logs}), queries
    status = m.project.get("search_status")
    if status not in ENUM["search_applicability"]:
        res.e(f"search_status 必须是 {'/'.join(ENUM['search_applicability'])}")
    elif queries and status == "not_applicable":
        res.e("有实际检索，但 search_status 声明为 not_applicable")
    elif not queries and status != "not_applicable":
        res.e("没有任何检索记录（覆盖为 0）；确实不需要检索时声明 search_status=not_applicable 并写理由")
    if status and not m.project.get("search_reason"):
        res.e("search_reason 为空")


def check_data(m, res):
    base, status = m.base, m.project.get("data_status")
    data = base / "data"
    if status not in ENUM["data_status"]:
        res.e(f"data_status 必须是 {'/'.join(ENUM['data_status'])}")
        return
    if not m.project.get("data_reason"):
        res.e("data_reason 为空")
    csvs = sorted(p for p in data.rglob("*.csv") if p.name != "dictionary.csv") if data.is_dir() else []
    res.stats.update(datasets=0, data_records=0, derived_records=0)
    if status != "available":
        if csvs or (data / "datasets.json").exists():
            res.e(f"data_status={status}，但 data 下有数据文件：要么改成 available，要么删掉数据")
        return
    if not (data / "README.md").is_file():
        res.e("缺少 data/README.md")
    try:
        datasets = json.loads((data / "datasets.json").read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        datasets = None
    if not isinstance(datasets, list) or not datasets:
        res.e("data/datasets.json 必须是非空数组")
        datasets = []
    dheader, drows = read_csv(data / "dictionary.csv", res, "data/dictionary.csv") if (data / "dictionary.csv").is_file() else (None, [])
    dictionary = {}
    if dheader is None:
        res.e("缺少 data/dictionary.csv")
    else:
        for c in DICT_COLS:
            if c not in dheader:
                res.e(f"dictionary.csv 缺少列 {c}")
        for r in drows:
            key = (r.get("dataset_id"), r.get("field"))
            if key in dictionary:
                res.e(f"dictionary.csv 重复登记 {key[0]}.{key[1]}")
            if any(not (r.get(c) or "").strip() for c in DICT_COLS):
                res.e(f"dictionary.csv 中 {key[0]}.{key[1]} 有空单元格")
            if r.get("type") not in ("string", "number", "boolean"):
                res.e(f"dictionary.csv 中 {key[0]}.{key[1]} 的 type 只能是 string、number、boolean")
            dictionary[key] = r
    records, paths, ids, used_dict = {}, set(), set(), set()
    for ds in datasets:
        if not isinstance(ds, dict) or any(not isinstance(ds.get(k), str) or not ds.get(k).strip()
                                           for k in ("id", "path", "stage", "grain", "coverage", "limitations")):
            res.e(f"datasets.json 条目缺少字段或有空值：{ds}")
            continue
        if ds["id"] in ids or ds["path"] in paths:
            res.e(f"datasets.json 中 id 或 path 重复：{ds['id']}")
        ids.add(ds["id"])
        paths.add(ds["path"])
        if ds["stage"] not in ("extracted", "curated") or not ds["path"].startswith(f"data/{ds['stage']}/") or not ds["path"].endswith(".csv"):
            res.e(f"数据集 {ds['id']}：stage 与路径不符（必须是 data/<stage>/….csv）")
            continue
        p = safe_path(base, ds["path"])
        if p is None:
            res.e(f"数据集 {ds['id']}：路径非法或文件不存在")
            continue
        header, rows = read_csv(p, res, ds["path"])
        if header is None:
            continue
        missing = [c for c in COMMON if c not in header]
        if missing:
            res.e(f"{ds['path']}：缺少公共字段 {'、'.join(missing)}")
            continue
        if not rows:
            res.e(f"{ds['path']}：空表（空壳）")
        res.stats["datasets"] += 1
        for col in header:
            if (ds["id"], col) not in dictionary:
                res.e(f"{ds['path']}：字段 {col} 没有在 dictionary.csv 登记")
            used_dict.add((ds["id"], col))
        for r in rows:
            check_record(r, ds, dictionary, records, m, res)
    for key in sorted(set(dictionary) - used_dict):
        if key[0] in ids:
            res.e(f"dictionary.csv 登记了 {key[0]}.{key[1]}，但数据集里没有这一列")
    for p in csvs:
        rel = p.relative_to(base).as_posix()
        if rel not in paths:
            res.e(f"{rel}：没有在 datasets.json 登记（孤立数据表）")
    # 血缘：输入存在、有值结果不依赖缺失输入、无环（Kahn 拓扑消去）
    for rid, (r, _) in records.items():
        for inp in [x.strip() for x in (r.get("input_ids") or "").split(";") if x.strip()]:
            if inp not in records:
                res.e(f"记录 {rid}：输入 {inp} 不存在")
            elif r.get("status") == "present" and records[inp][0].get("status") != "present":
                res.e(f"记录 {rid}：有值结果依赖了没有值的输入 {inp}")
    indeg = {rid: 0 for rid in records}
    edges = {rid: [] for rid in records}
    for rid, (r, _) in records.items():
        for inp in [x.strip() for x in (r.get("input_ids") or "").split(";") if x.strip()]:
            if inp in records:
                edges[inp].append(rid)
                indeg[rid] += 1
    queue = [k for k, v in indeg.items() if v == 0]
    while queue:
        k = queue.pop()
        for nxt in edges[k]:
            indeg[nxt] -= 1
            if indeg[nxt] == 0:
                queue.append(nxt)
    cyclic = sorted(k for k, v in indeg.items() if v > 0)
    if cyclic:
        res.e(f"数据血缘有循环依赖：{'、'.join(cyclic[:10])}")
    m.records = records


def check_record(r, ds, dictionary, records, m, res):
    rid = (r.get("record_id") or "").strip()
    at = f"{ds['path']} 记录 {rid or '（空 ID）'}"
    if not rid:
        res.e(f"{at}：record_id 为空")
    elif rid in records:
        res.e(f"{at}：record_id 在全包范围内重复")
    for col, value in r.items():
        t = (dictionary.get((ds["id"], col)) or {}).get("type")
        if value and t == "number":
            try:
                if not Decimal(value).is_finite():
                    raise InvalidOperation
            except InvalidOperation:
                res.e(f"{at}：{col}={value} 不是有限数")
        if value and t == "boolean" and value not in ("true", "false"):
            res.e(f"{at}：{col}={value} 不是 true/false")
    status, value, vtype, origin = r.get("status"), r.get("value", ""), r.get("value_type"), r.get("value_origin")
    if status not in ("present", "missing", "unavailable", "not_applicable"):
        res.e(f"{at}：status={status} 无效")
    if status == "present" and value == "":
        res.e(f"{at}：present 记录的 value 为空")
    if status in ("missing", "unavailable", "not_applicable") and (value != "" or not (r.get("missing_reason") or "").strip()):
        res.e(f"{at}：没有值的记录要留空 value 并写 missing_reason（不能填 0）")
    if vtype not in ("number", "string", "boolean"):
        res.e(f"{at}：value_type={vtype} 无效")
    if vtype == "number" and status == "present":
        try:
            if not Decimal(value).is_finite():
                raise InvalidOperation
        except InvalidOperation:
            res.e(f"{at}：数值 {value} 不是有限数（不能混写单位）")
    if vtype == "number":
        empty = [c for c in NUMERIC_CONTEXT if not (r.get(c) or "").strip()]
        if empty:
            res.e(f"{at}：数值记录缺少口径字段 {'、'.join(empty)}")
    if vtype == "boolean" and status == "present" and value not in ("true", "false"):
        res.e(f"{at}：布尔值必须是 true/false")
    if origin not in ("reported", "estimate", "derived"):
        res.e(f"{at}：value_origin={origin} 无效")
    if ds["stage"] == "extracted":
        if origin == "derived" or r.get("input_ids") or r.get("method"):
            res.e(f"{at}：提取层不能有派生字段（value_origin=derived、input_ids、method）")
        if status == "present":
            snap = m.snapshots.get(r.get("source_id"))
            if snap is None:
                res.e(f"{at}：source_id={r.get('source_id')} 没有快照")
            if not (r.get("source_locator") or "").strip() or not (r.get("original_value") or "").strip():
                res.e(f"{at}：有值的提取记录要写 source_locator 和 original_value")
            if snap and snap["meta"].get("access") not in ("full", "partial") and not snap["meta"].get("original_files"):
                res.e(f"{at}：来源 {r.get('source_id')} 既没有完整正文也没有原件，提取值无法核对")
    else:
        if not (r.get("input_ids") or "").strip() or not (r.get("method") or "").strip():
            res.e(f"{at}：整理层必须写 input_ids 和 method（原样选用也要写）")
        if r.get("source_id") or r.get("source_locator"):
            res.e(f"{at}：整理层不能直接写来源，通过 input_ids 追溯")
        method = r.get("method") or ""
        if method and not method.startswith("analysis/"):
            res.e(f"{at}：method 必须指向 analysis/ 下的文件")
        elif method and safe_path(m.base, method) is None:
            res.e(f"{at}：method 文件 {method} 路径非法或不存在")
        if origin == "derived":
            res.stats["derived_records"] += 1
    if rid:
        records[rid] = (r, ds)
        res.stats["data_records"] += 1


CITE = re.compile(r"\[(\d+(?:\s*[-–,，]\s*\d+)*)(?:,[^\]]*)?\](?!\()")
REF_LINE = re.compile(r"^- \[(\d+)\] (.+)$")
REF_TAIL = re.compile(r"来源 ID `([^`]+)` 存档 \[[^\]]*\]\(([^)]+)\)\s*$")
DATA_LINK = re.compile(r"\[数据:([^\]]+)\]\(([^)]+)\)")


def check_report(m, res, data_available):
    if m.report_path is None or not m.report_path.is_file():
        return
    text = m.report_path.read_text(encoding="utf-8-sig")
    head, sep, refs = text.partition("## 参考来源")
    if not sep:
        res.e("report.md 缺少「## 参考来源」一节")
    entries, cited_sources = {}, set()
    for line in refs.splitlines():
        mm = REF_LINE.match(line.strip())
        if not mm:
            continue
        n = int(mm.group(1))
        if n in entries:
            res.e(f"参考条目编号重复：[{n}]")
        tail = REF_TAIL.search(mm.group(2))
        if not tail:
            res.e(f"参考条目 [{n}] 行尾无法解析（要写 来源 ID `X001` 存档 [文件](路径)）")
            continue
        sid, link = tail.group(1), tail.group(2)
        entries[n] = sid
        target = safe_path(m.report_path.parent, link) if not link.startswith("../") else _resolve(m.report_path.parent, link, m.root)
        snap = m.snapshots.get(sid)
        if target is None:
            res.e(f"参考条目 [{n}]：链接 {link} 非法或文件不存在")
        elif snap is None:
            res.e(f"参考条目 [{n}]：来源 {sid} 没有快照")
        elif target != (m.base / snap["path"]).resolve():
            res.e(f"参考条目 [{n}]：链接与来源 {sid} 的快照不对应")
        elif snap["meta"].get("access") not in ("full", "partial"):
            res.w(f"参考条目 [{n}]：来源 {sid} 的正文不完整（{snap['meta'].get('access')}），须人工核对原件或其他支撑来源")
    body = re.sub(r"```.*?```", "", head, flags=re.S)
    body = re.sub(r"`[^`\n]*`", "", body)
    used = set()
    for mm in CITE.finditer(body):
        nums = []
        for part in re.split(r"[,，]", mm.group(1)):
            bounds = [int(x) for x in re.split(r"\s*[-–]\s*", part.strip()) if x]
            nums += list(range(bounds[0], bounds[-1] + 1)) if len(bounds) == 2 and bounds[1] - bounds[0] < 50 else bounds
        if all(1900 <= x <= 2100 and x not in entries for x in nums):
            continue                                       # [2024] 这类年份方括号
        for x in nums:
            used.add(x)
            if x not in entries:
                res.e(f"正文引用了参考列表里没有的 [{x}]")
    for n in sorted(set(entries) - used):
        res.w(f"参考条目 [{n}] 没有被正文引用")
    if not entries or not used:
        res.e("正文没有任何引用，或参考列表为空（覆盖为 0）")
    cited_sources = {entries[n] for n in used if n in entries}
    links = 0
    records = getattr(m, "records", {})
    for mm in DATA_LINK.finditer(body):
        links += 1
        rid, link = mm.group(1), mm.group(2)
        target = safe_path(m.report_path.parent, link) if not link.startswith("../") else _resolve(m.report_path.parent, link, m.root)
        if target is None:
            res.e(f"数据关联 {rid}：路径 {link} 非法或文件不存在")
        elif rid not in records:
            res.e(f"数据关联 {rid}：记录不存在")
        elif target != (m.base / records[rid][1]["path"]).resolve():
            res.e(f"数据关联 {rid}：路径与记录所在数据集不一致")
    if data_available and not links:
        res.e("data_status=available，但报告正文没有任何 [数据:记录ID](路径) 关联")
    res.stats.update(reference_entries=len(entries), cited_sources=len(cited_sources), report_data_links=links)


def _resolve(base_dir, link, root):
    """任务文件夹里报告的链接（如 ../03_evidence/raw/…）：解析后必须在任务文件夹内。"""
    if "\\" in link:
        return None
    p = (pathlib.Path(base_dir) / link).resolve()
    try:
        p.relative_to(pathlib.Path(root).resolve())
    except ValueError:
        return None
    return p if p.is_file() else None


def check_key_claims(m, res):
    """弱检查（以警告输出）：影响结论的主张，独立来源数和有没有一手、S/A 级来源。"""
    if m.kind != "task":
        return
    for c in m.claims:
        if not c.get("affects_conclusion"):
            continue
        srcs = {m.evidence_rows[l["evidence_id"]]["source_id"] for l in m.claim_links
                if l["claim_id"] == c["id"] and l["relation"] == "supports" and l["evidence_id"] in m.evidence_rows}
        rows = [m.ledger_sources[s] for s in srcs if s in m.ledger_sources]
        groups = {r.get("origin_group") or r["id"] for r in rows}
        strong = any(r.get("tier") == "primary" and r.get("grade") in ("S", "A") for r in rows)
        weak_only = all(r.get("access") not in ("full", "partial") for r in rows) if rows else True
        if len(groups) < 2 and not strong:
            res.w(f"关键主张 {c['id']}：只有 {len(groups)} 个独立来源，且没有一手 S/A 级来源")
        if rows and weak_only:
            res.w(f"关键主张 {c['id']}：支撑来源都不是完整正文，不能单独支撑关键结论")


def check_size(root, res):
    total = sum(p.stat().st_size for p in pathlib.Path(root).rglob("*") if p.is_file())
    if total > PACKAGE_LIMIT:
        res.w(f"总体积 {total // (1024 * 1024)}MB 超过 500MB：暂停问用户（精简范围、换压缩方式或接受体积）")


def check_final(root, res, sealing=False):
    root = pathlib.Path(root)
    current = digest(root)
    try:
        review = json.loads((root / "qa" / "review.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        review = None
    if not isinstance(review, dict):
        res.e("qa/review.json 缺失或不是对象")
    else:
        if not str(review.get("reviewer") or "").strip():
            res.e("review.json 的 reviewer 为空")
        if review.get("reviewed_digest") != current:
            res.e("人工复核已过期：review.json 的 reviewed_digest 与当前内容指纹不一致，内容改过要重新复核")
        for k in ("questions_answered", "evidence_support", "data_semantics", "limitations"):
            item = (review.get("checks") or {}).get(k)
            if not isinstance(item, dict) or item.get("passed") is not True or not str(item.get("evidence") or "").strip():
                res.e(f"review.json 的 {k} 没有通过或没写核验依据")
    readme = (root / "README.md").read_text(encoding="utf-8") if (root / "README.md").is_file() else ""
    s, e = readme.count(STATS_START), readme.count(STATS_END)
    if s != 1 or e != 1 or readme.find(STATS_START) > readme.find(STATS_END):
        res.e("README.md 的统计标记必须各有一个，且 start 在 end 之前")
    if sealing:
        return current
    mf = root / "manifest-sha256.txt"
    if not mf.is_file():
        res.e("没有 manifest-sha256.txt（还没封包）")
    else:
        listed = {}
        for n, line in enumerate(mf.read_text(encoding="utf-8").splitlines(), 1):
            mm = re.fullmatch(r"([0-9a-f]{64})  (.+)", line)
            if not mm:
                res.e(f"manifest 第 {n} 行格式无法解析")
                continue
            path = mm.group(2)
            if path in listed or path == "manifest-sha256.txt":
                res.e(f"manifest 第 {n} 行：路径重复或列了清单自身")
            listed[path] = mm.group(1)
            p = safe_path(root, path)
            if p is None:
                res.e(f"manifest：{path} 非法或文件不存在")
            elif sha(p) != mm.group(1):
                res.e(f"manifest：{path} 的哈希不一致（封包后被改动）")
        if not listed:
            res.e("manifest 为空")
        for p in all_files(root, {"manifest-sha256.txt"}):
            if p not in listed:
                res.e(f"manifest 没有覆盖 {p}（封包后新增的文件）")
    try:
        checks = json.loads((root / "qa" / "checks.json").read_text(encoding="utf-8"))
        if checks.get("status") != "FINALIZED" or checks.get("reviewed_digest") != current:
            res.e("qa/checks.json 的状态不是 FINALIZED，或指纹已过期")
    except (OSError, ValueError, AttributeError):
        res.e("qa/checks.json 缺失或无法解析")
    return current


def seal(root, result, current):
    """写 README 统计区、qa/checks.json，最后写 manifest（覆盖除自身外的全部文件）。"""
    root = pathlib.Path(root)
    readme = (root / "README.md").read_text(encoding="utf-8")
    table = ["已通过自动检查和人工复核；最终状态以重新运行 --final 为准。", "", "| 统计项 | 数值 |", "|---|---|"]
    table += [f"| {k} | {result['stats'].get(k, 0)} |" for k in STATS_KEYS]
    start, end = readme.index(STATS_START) + len(STATS_START), readme.index(STATS_END)
    (root / "README.md").write_text(readme[:start] + "\n" + "\n".join(table) + "\n" + readme[end:], encoding="utf-8")
    (root / "qa").mkdir(exist_ok=True)
    (root / "qa" / "checks.json").write_text(json.dumps({**result, "status": "FINALIZED", "reviewed_digest": current}, ensure_ascii=False, indent=2) + "\n",
                                             encoding="utf-8")
    lines = [f"{sha(root / p)}  {p}" for p in all_files(root, {"manifest-sha256.txt"})]
    (root / "manifest-sha256.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---------- 入口 ----------

def run(target, final=False, write_manifest=False, profile="full"):
    target = pathlib.Path(target)
    res = Result()
    is_task = (target / "03_evidence").is_dir() and not (target / "package.json").exists()
    roots = [target / "03_evidence", target / "03r_research"] if is_task else [target]
    links = [p for r in roots if r.exists() for p in symlinks(r)]
    if links:
        res.e("不允许符号链接：" + "、".join(str(p) for p in links[:5]))
        return finish(res, final or write_manifest, 1)
    if profile == "lite":
        m = Model("lite", target, target)
        check_sources(m, res, lite=True)
        answer = target / "answer.md"
        if not answer.is_file() or not answer.read_text(encoding="utf-8").strip():
            res.e("轻量包缺少 answer.md 或内容为空")
        else:
            ids = set(re.findall(r"\b[ABD-Z]\d{3,4}\b", answer.read_text(encoding="utf-8")))
            if not ids:
                res.e("answer.md 没有引用任何来源 ID")
            for sid in sorted(ids - set(m.snapshots)):
                res.e(f"answer.md 引用的 {sid} 没有快照")
        return finish(res, False, 1)
    try:
        if is_task:
            if final or write_manifest:
                res.e("--final 和 --write-manifest 只用于研究包；任务文件夹请用 research seal 封包")
                return finish(res, True, 1)
            m = load_task(target, res)
            for rel in TASK_REQUIRED:
                p = target / rel
                if not p.is_file() or not p.read_text(encoding="utf-8").strip():
                    res.e(f"缺少 {rel} 或内容为空")
            version = 2
        else:
            m = load_package(target, res)
            if getattr(m, "legacy", False):
                res.w("legacy 包：只读诊断，不迁移、不封包、不宣称符合 v2")
                return finish(res, final or write_manifest, 1)
            for rel in PACKAGE_REQUIRED:
                p = target / rel
                if not p.is_file() or not p.read_text(encoding="utf-8").strip():
                    res.e(f"缺少 {rel} 或内容为空")
            version = 2
        check_sources(m, res)
        check_evidence(m, res)
        check_logs(m, res)
        check_data(m, res)
        check_report(m, res, m.project.get("data_status") == "available")
        check_key_claims(m, res)
        check_size(target, res)
        current = None
        if final or write_manifest:
            current = check_final(target, res, sealing=write_manifest)
    except (OSError, UnicodeError, ValueError, TypeError, KeyError) as e:
        res.e(f"文件或格式错误：{type(e).__name__}: {e}")
        return finish(res, final or write_manifest, 2)
    result = finish(res, final or write_manifest, version)
    if write_manifest and not res.errors:
        if (target / "manifest-sha256.txt").exists():
            result["errors"].append("已经封包（存在 manifest），不能再次写入；要修订请新建修订版")
            result["status"] = "FAIL"
        else:
            seal(target, result, current)
    return result


def finish(res, final_mode, version):
    status = "FAIL" if res.errors else ("PASS_FINAL" if final_mode else "PASS_AUTOMATED")
    return {"schema_version": version, "status": status, "errors": res.errors, "warnings": res.warnings, "stats": res.stats,
            "manual_review": ("blocked" if res.errors else "recorded") if final_mode else "required",
            "checked_at": datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()}
