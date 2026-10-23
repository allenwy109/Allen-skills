"""研究包封包（research seal，设计 §5.1）。分两步，中间是人工复核：

prepare：选范围 → 在 03r_research/.staging-<包ID>/ 按上游 v2 布局组装 → 自动检查零错误 → 打印内容指纹
  （复核人在暂存副本上实际复核，把结论写进证据账 reviews 表：type=research_review，digest=这个指纹，checks 写 4 项）
publish：导出 qa/review.json → --write-manifest → --final → 原子移动到 08_deliverables/research-package/<包ID>/ →
  在包外生成 <包ID>.zip → 登记验收

范围：默认收入全部有快照的来源（读过且相关的，无论是否被引用）、全部证据、全部检索日志、数据和方法；
--slim 只收被报告引用的来源和它们依赖的数据（用户明确要求精简时用，README 会写明）。
任何一步失败都不发布，暂存目录保留供诊断。已发布的包不可改；修订用 --revise-of <旧包ID>，新包 ID 加 -r2、-r3，写 supersedes。
"""
import datetime
import json
import os
import pathlib
import re
import shutil

import rcheck
from tools.acceptance import Acceptance
from tools.lib import schema_check, snapshot
from tools.lib.ledger import Ledger

ENUMS = schema_check.load("ledger.schema.json")["enums"]


class SealError(Exception):
    pass


def _label(enum, v):
    return ENUMS[enum]["labels"].get(v, v) if v else "—"


def staging_dir(task, pid):
    return pathlib.Path(task) / "03r_research" / f".staging-{pid}"


def published_dir(task, pid):
    return pathlib.Path(task) / "08_deliverables" / "research-package" / pid


def _pkg_path(path):
    """任务文件夹 03_evidence 下的路径 → 包内路径（用户材料目录改名为 raw/user-provided）。"""
    return re.sub(r"^raw/user/", "raw/user-provided/", path)


def _write_snapshot(dest, meta, body):
    lines = ["---"] + [f"{k}: {json.dumps(meta.get(k), ensure_ascii=False)}" for k in rcheck.PACKAGE_META] + ["---", ""]
    dest.write_text("\n".join(lines) + body, encoding="utf-8")


def _copytree(src, dest):
    if src.is_dir():
        shutil.copytree(src, dest, dirs_exist_ok=True)


def prepare(task, slug=None, slim=False, revise_of=None):
    task = pathlib.Path(task)
    led = Ledger(task)
    proj = (led.read("project") or [{}])[0]
    if revise_of:
        n = 2
        while published_dir(task, f"{revise_of}-r{n}").exists():
            n += 1
        pid = f"{revise_of}-r{n}"
    else:
        if not slug or not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,39}", slug):
            raise SealError("要给 --slug（小写英文或拼音，≤40 字符）")
        pid = f"{datetime.date.today().isoformat()}-{slug}"
    if published_dir(task, pid).exists():
        raise SealError(f"{published_dir(task, pid)} 已发布，不能覆盖；要修订用 --revise-of {pid}")
    pre = rcheck.run(task)
    if pre["errors"]:
        raise SealError("任务文件夹的检查没有通过，先修好再封包：\n" + "\n".join(f"- {e}" for e in pre["errors"]))
    st = staging_dir(task, pid)
    if st.exists():
        shutil.rmtree(st)
    st.mkdir(parents=True)
    ev, rs = task / "03_evidence", task / "03r_research"
    sources = {s["id"]: s for s in led.read("sources") if s.get("snapshot")}
    report = (rs / "report.md").read_text(encoding="utf-8")
    refs = {}
    for line in report.partition("## 参考来源")[2].splitlines():
        m = re.match(r"^- \[(\d+)\] .*来源 ID `([^`]+)`", line.strip())
        if m:
            refs.setdefault(m.group(2), []).append(int(m.group(1)))
    keep = set(sources)
    if slim:
        keep = set(refs)
        for csvf in (ev / "data" / "extracted").glob("*.csv") if (ev / "data" / "extracted").is_dir() else []:
            _, rows = rcheck.read_csv(csvf, rcheck.Result(), str(csvf))
            keep |= {r.get("source_id") for r in rows if r.get("source_id")}
        missing = keep - set(sources)
        if missing:
            raise SealError(f"依赖不闭合：这些来源被引用但没有快照：{'、'.join(sorted(missing))}")
    # 包元数据
    doc = {"schema_version": 2, "package_id": pid, "topic": proj.get("question") or slug or pid,
           "information_cutoff": proj.get("information_cutoff") or datetime.date.today().isoformat(),
           "data_status": proj.get("data_status"), "data_reason": proj.get("data_reason"),
           "search_status": proj.get("search_status"), "search_reason": proj.get("search_reason")}
    if revise_of:
        doc["supersedes"] = revise_of
    (st / "package.json").write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    # 快照（补齐评价字段）与原件
    (st / "raw" / "sources").mkdir(parents=True)
    for sid in sorted(keep):
        s = sources[sid]
        meta, body = snapshot.read(ev / s["snapshot"])
        full = {k: s.get(k) for k in rcheck.PACKAGE_META}
        full.update(meta)
        for k in ("author_org", "published", "language", "url", "final_url"):
            if full.get(k) in (None, ""):
                full[k] = "unknown" if k not in ("url", "final_url") or s["origin"] != "user" else f"file:{(s.get('original_files') or [{}])[0].get('path', '')}"
        full["conflict_of_interest"] = full.get("conflict_of_interest") or "none"
        full["research_line"] = full.get("research_line") or "M"
        full["access_note"] = full.get("access_note") or "正常"
        full["rights_note"] = full.get("rights_note") or "none"
        full["subquestions"] = full.get("subquestions") or []
        full["original_files"] = [{"path": _pkg_path(o["path"]), "sha256": o["sha256"]} for o in meta.get("original_files") or []]
        _write_snapshot(st / _pkg_path(s["snapshot"]), full, body)
        for o in meta.get("original_files") or []:
            dest = st / _pkg_path(o["path"])
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ev / o["path"], dest)
    # 来源索引（由证据账和快照生成）
    rows = ["# 来源索引", "", "| " + " | ".join(rcheck.INDEX_COLUMNS) + " |", "|" + "---|" * len(rcheck.INDEX_COLUMNS)]
    for sid in sorted(keep):
        s = sources[sid]
        files = [_pkg_path(s["snapshot"])] + [_pkg_path(o["path"]) for o in s.get("original_files") or []]
        note = "；".join(x for x in (f"supersedes {s['supersedes']}" if s.get("supersedes") else "", f"重复→{s['duplicate_of']}" if s.get("duplicate_of") else "",
                                      "内部资料" if s.get("internal") or s["origin"] == "user" else "", s.get("access_note") if s.get("access_note") not in (None, "正常") else "") if x)
        cells = [sid, s["title"], s.get("author_org") or "unknown", s.get("published") or "unknown", s["accessed"], _label("tier", s.get("tier")),
                 s.get("grade") or "—", _label("access", s.get("access")), _label("capture_method", s.get("capture_method")), "；".join(files),
                 s.get("final_url") or s.get("url") or "—", "".join(f"[{n}]" for n in refs.get(sid, [])) or "—", note or "—"]
        rows.append("| " + " | ".join(str(c).replace("|", "／") for c in cells) + " |")
    (st / "sources.md").write_text("\n".join(rows) + "\n", encoding="utf-8")
    # 报告、数据、方法
    (st / "report.md").write_text(report.replace("](../03_evidence/raw/user/", "](raw/user-provided/").replace("](../03_evidence/", "]("), encoding="utf-8")
    _copytree(ev / "data", st / "data")
    _copytree(ev / "analysis", st / "analysis")
    # 证据块与检索日志（由证据账生成）
    by_line = {}
    for e in led.read("evidence"):
        if e["source_id"] in keep:
            by_line.setdefault(e.get("research_line") or "M", []).append(e)
    if by_line:
        (st / "notes").mkdir()
    for line, evs in sorted(by_line.items()):
        out = [f"# 研究线 {line} 的证据块", ""]
        for e in evs:
            out += [f"## {e['id']} {e.get('claim_text') or e['excerpt'][:20]}", f"- 论断: {e.get('claim_text') or '—'}",
                    f"- 来源: `{e['source_id']}` · 定位: {e['locator']}", "- 逐字摘录:"]
            out += [f"  > {seg}" for seg in e["excerpt"].splitlines()]
            out += [f"- 解读: {e.get('interpretation') or '—'}", f"- 用于: {'、'.join(e.get('used_in') or []) or 'none'}",
                    f"- 交叉来源: {'、'.join(e.get('cross_sources') or []) or 'none'}", ""]
        (st / "notes" / f"{line}-evidence.md").write_text("\n".join(out), encoding="utf-8")
    work = st / "work"
    work.mkdir()
    for name in ("brief.md", "plan.md"):
        shutil.copy2(rs / name, work / name)
    _copytree(rs / "tasks", work / "tasks")
    logs = {}
    for q in led.read("search_log"):
        logs.setdefault(q["research_line"], []).append(q)
    if logs:
        (work / "search-logs").mkdir()
    for line, qs in sorted(logs.items()):
        out = [f"# 研究线 {line} 的检索日志", ""]
        for q in sorted(qs, key=lambda x: x["searched_at"]):
            dis = "；".join(f"{d['target']}（{_label('discard_reason', d['reason'])}）" for d in q.get("discarded") or []) or "无"
            out += [f"## {q['searched_at']} · {q['tool']}", f"- 查询原文: `{q['query']}`", f"- 过滤: {q.get('filters') or '无'}",
                    f"- 看过的结果: {q.get('results_seen') or '—'}", f"- 打开并存档: {'、'.join(q.get('opened_source_ids') or []) or '无'}", f"- 弃用: {dis}", ""]
        (work / "search-logs" / f"{line}.md").write_text("\n".join(out), encoding="utf-8")
    (st / "qa").mkdir()
    (st / "README.md").write_text(_readme(doc, proj, slim), encoding="utf-8")
    result = rcheck.run(st)
    if result["errors"]:
        raise SealError("暂存目录的自动检查没有通过（暂存目录保留在 " + str(st) + "）：\n" + "\n".join(f"- {e}" for e in result["errors"]))
    return {"package_id": pid, "staging": str(st), "digest": rcheck.digest(st), "warnings": result["warnings"], "stats": result["stats"]}


def _readme(doc, proj, slim):
    return f"""# 研究包：{doc['topic']}

| 项 | 内容 |
|---|---|
| 研究问题 | {proj.get('question') or doc['topic']} |
| 信息截止 | {doc['information_cutoff']} |
| 包 ID | {doc['package_id']} |
| 范围 | {'按用户要求精简：只含被引用的来源和检索日志' if slim else '全部读过且相关的来源、证据、检索日志与数据'} |

## 三个入口

- 报告：[report.md](report.md)
- 数据：{'[data/README.md](data/README.md)' if doc['data_status'] == 'available' else '无结构化数据（' + (doc.get('data_reason') or '') + '）'}
- 核验：[sources.md](sources.md)、notes/、work/search-logs/、[qa/review.json](qa/review.json)

## 检查统计

{rcheck.STATS_START}
{rcheck.STATS_END}

## 自动检查与人工复核

自动检查只能证明文件、字段、引用、摘录和血缘关系齐全一致，不能证明数字抄对、来源独立、口径可比或结论成立；这些由人工复核负责，结果写在 qa/review.json，并用内容指纹绑定。

## 版权与保密

原始材料版权归原作者，仅供内部研究和核验，对外分发前要确认授权。标为"内部资料"的来源、以及报告、笔记、数据表本身都可能含内部信息。

## 完整性验证

在包目录运行 `research check <包目录> --final`，或 `shasum -a 256 -c manifest-sha256.txt`。包发布后不可修改；更新时新建修订版。
"""


def publish(task, pid):
    task = pathlib.Path(task)
    st = staging_dir(task, pid)
    if not st.is_dir():
        raise SealError(f"没有暂存目录 {st}：先运行 seal --prepare")
    dest = published_dir(task, pid)
    if dest.exists():
        raise SealError(f"{dest} 已发布，不能覆盖")
    current = rcheck.digest(st)
    reviews = [r for r in Ledger(task).read("reviews") if r.get("type") == "research_review" and r.get("digest") == current]
    if not reviews:
        raise SealError(f"没有针对当前暂存副本的人工复核：在证据账 reviews 表登记 type=research_review、digest={current}，"
                        "checks 写 questions_answered、evidence_support、data_semantics、limitations 四项（passed 和核验依据）")
    r = reviews[-1]
    (st / "qa" / "review.json").write_text(json.dumps({"reviewer": r["reviewer"], "reviewed_digest": current, "reviewed_at": r["at"],
                                                       "conclusion": r["conclusion"], "checks": r.get("checks") or {}}, ensure_ascii=False, indent=2) + "\n",
                                          encoding="utf-8")
    sealed = rcheck.run(st, write_manifest=True)
    if sealed["errors"]:
        raise SealError("封包检查没有通过（没有写任何文件）：\n" + "\n".join(f"- {e}" for e in sealed["errors"]))
    final = rcheck.run(st, final=True)
    if final["errors"]:
        raise SealError("--final 没有通过：\n" + "\n".join(f"- {e}" for e in final["errors"]))
    dest.parent.mkdir(parents=True, exist_ok=True)
    os.replace(st, dest)
    archive = shutil.make_archive(str(dest), "zip", root_dir=dest.parent, base_dir=pid)
    entry = Acceptance(task).record({
        "id": f"research-{pid}".lower(), "kind": "research_package", "title": f"研究包 {pid}",
        "files": [str(pathlib.Path(archive).relative_to(task))],
        "upstream_checks": [{"name": "research check --final", "result": "passed",
                             "detail": f"快照 {final['stats'].get('snapshots_parsed')}、摘录 {final['stats'].get('quotes_checked')}、检索 {final['stats'].get('search_queries')}、数据记录 {final['stats'].get('data_records')}"}],
        "number_trace": {"checked": 0, "untraced": []}})
    return {"package": str(dest), "zip": archive, "final": final, "acceptance": entry["status"]}
