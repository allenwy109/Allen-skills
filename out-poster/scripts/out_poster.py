#!/usr/bin/env python3
"""出一页海报（设计 §6.2 out-poster）。onepager 没有渲染器，HTML 由作者照模板手写，所以分两步：

  prepare  建 onepager 项目，并从证据账生成"可用事实清单"facts.json（只含能进成品的主张和指标，数字已按显示规则算好）
  finish   作者写完 blueprint.json、onepager.ir.json 和 HTML 后：静态检查 → 渲染检查 → 截图 → 登记构建 →
           项目校验 → 数字回查 → 复制到 08_deliverables/poster/ → 登记验收

用法：
  python3 out_poster.py prepare <任务文件夹> --slug <英文短名> --title <标题> [--claims cl-0001,cl-0003]
  python3 out_poster.py finish  <任务文件夹> --slug <英文短名> --html <海报.html>
                                --A A2 --B B7 --C C2 --T T3 --E E1 --F <署名> [--allow 3]
项目目录：07_storyline/poster-work/<slug>/（onepager 的 manifest、source/facts.json、blueprint.json、onepager.ir.json、builds/）。
onepager 的 record-build 只接受静态检查和渲染检查都是 PASS；有 WARN 也要先修掉。
退出码：0 已出海报；1 被检查拦下；2 参数或环境错误。
"""
import argparse
import json
import os
import pathlib
import shutil
import subprocess
import sys

SKILL_DIR = pathlib.Path(__file__).resolve().parents[1]
SIZES = {"A1": ("800", "auto"), "A2": ("1920", "1080"), "A3": ("1080", "1080"), "A4": ("1080", "1440")}


def _bootstrap():
    for c in (os.environ.get("ALLEN_RUNTIME"), SKILL_DIR.parent / "_allen-runtime", SKILL_DIR.parent):
        if c and (pathlib.Path(c) / "tools" / "lib" / "runtime.py").is_file():
            sys.path.insert(0, str(pathlib.Path(c)))
            return
    raise SystemExit("找不到运行时（tools/lib），请先运行 ./install.sh")


_bootstrap()
from tools.acceptance import Acceptance  # noqa: E402
from tools.bridge import poster_numbers  # noqa: E402
from tools.lib import metrics as M  # noqa: E402
from tools.lib import runtime, schema_check  # noqa: E402
from tools.lib.ledger import Ledger  # noqa: E402


def project_dir(task, slug):
    return pathlib.Path(task) / "07_storyline" / "poster-work" / slug


def facts(task, claim_ids=None):
    led = Ledger(task)
    labels = schema_check.load("ledger.schema.json")["enums"]
    metrics = {m["id"]: m for m in led.read("metrics")}
    claims = led.read("claims")
    by_metric = M.claims_by_metric(claims)
    resolved = M.resolved_conflict_claims(led.read("conflicts"))
    sources = {s["id"]: s for s in led.read("sources")}
    links = led.read("claim_evidence")
    evidence = {e["id"]: e for e in led.read("evidence")}
    out, bignum = [], []
    for c in claims:
        if claim_ids and c["id"] not in claim_ids:
            continue
        if not M.presentable(c, resolved):
            continue
        mets = []
        for mid in c.get("metric_refs") or []:
            if M.check_presentable(mid, metrics, by_metric, resolved):
                continue
            shown = M.display(M.evaluate(metrics, mid), metrics[mid]["decimals"])
            mets.append({"metric": mid, "display": shown, "unit": metrics[mid]["unit"], "label": metrics[mid].get("label", "")})
            if c["verification"] in poster_numbers.BIGNUM_KINDS and c["kind"] in ("fact", "data"):
                bignum.append({"metric": mid, "display": shown, "unit": metrics[mid]["unit"], "claim": c["id"]})
        src = sorted({evidence[l["evidence_id"]]["source_id"] for l in links if l["claim_id"] == c["id"] and l["evidence_id"] in evidence})
        out.append({"claim": c["id"], "statement": c["statement"], "kind": labels["claim_kind"]["labels"][c["kind"]],
                    "verification": labels["verification"]["labels"][c["verification"]], "metrics": mets,
                    "sources": [f"{sources[s]['title']}（{s}）" for s in src if s in sources]})
    return {"claims": out, "bignum_candidates": bignum,
            "rules": ["只用本清单里的主张和数字；数字写成清单里 display 的值",
                      "非事实身份（估算、预测等）的数字，前后要注明身份",
                      "BigNumber 只用 bignum_candidates 里的指标，不足 2 个就改用 E2",
                      "页面要写来源；署名由调用方指定"]}


def run(cmd, cwd=None):
    p = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    return p.returncode, p.stdout, p.stderr


def prepare(a):
    task, d = pathlib.Path(a.task), project_dir(a.task, a.slug)
    if d.exists():
        print(f"项目已存在：{d}（同一主题的迭代沿用已有项目）")
        return 0
    d.parent.mkdir(parents=True, exist_ok=True)
    fact_file = d.parent / f"{a.slug}-facts.json"
    fact_file.write_text(json.dumps(facts(task, a.claims.split(",") if a.claims else None), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    engine = runtime.engine_dir("onepager", skill_dir=SKILL_DIR)
    code, out, err = run([str(runtime.venv_python()), str(engine / "scripts" / "project.py"), "init", str(d),
                          "--slug", a.slug, "--title", a.title, "--source", str(fact_file)])
    if code != 0:
        print(f"建项目失败：{(out + err)[-300:]}", file=sys.stderr)
        return 2
    print(f"已建项目：{d}")
    print(f"可用事实清单：{d / 'source' / fact_file.name}")
    print("下一步：按 UPSTREAM-SKILL.md 第 3–4 阶段写 blueprint.json、onepager.ir.json 和 HTML（都放在项目目录），然后运行 finish。")
    return 0


def finish(a):
    task, d = pathlib.Path(a.task), project_dir(a.task, a.slug)
    html = pathlib.Path(a.html)
    if not d.is_dir() or not html.is_file():
        print("项目目录或 HTML 不存在，先运行 prepare 并写好 HTML", file=sys.stderr)
        return 2
    for name in ("blueprint.json", "onepager.ir.json"):
        if not (d / name).is_file():
            print(f"缺少 {d / name}", file=sys.stderr)
            return 2
    engine, py = runtime.engine_dir("onepager", skill_dir=SKILL_DIR), str(runtime.venv_python())
    scripts = engine / "scripts"
    checks_dir = d / "checks"
    checks_dir.mkdir(exist_ok=True)
    checks = []

    def engine_check(name, cmd, out_file):
        code, out, err = run(cmd)
        try:
            report = json.loads(out)
        except ValueError:
            checks.append({"name": name, "result": "failed", "detail": (out + err)[-300:]})
            return False
        out_file.write_text(out, encoding="utf-8")
        verdict = report.get("verdict")
        detail = "；".join(report.get("errors", []) + report.get("warnings", []))[:500]
        if verdict == "PASS":
            checks.append({"name": name, "result": "passed", "detail": "PASS"})
            return True
        note = "（onepager 只接受 PASS 的构建，警告也要修掉）" if verdict == "WARN" else ""
        checks.append({"name": name, "result": "failed", "detail": f"{verdict}{note}：{detail}"})
        return False

    static = checks_dir / "static-check.json"
    render = checks_dir / "render-check.json"
    q = [py, str(scripts / "quality_check.py"), str(html), "--style", a.B, "--size", a.A, "--format", "json"]
    if a.E == "E2":
        q.append("--no-bignum")
    ok = engine_check("quality_check", q, static)
    ok = engine_check("render_check", [py, str(scripts / "render_check.py"), str(html), "--size", a.A, "--format", "json"], render) and ok
    trace = poster_numbers.check(task, html.read_text(encoding="utf-8"), a.allow)
    checks.append({"name": "数字回查", "result": "failed" if trace["untraced"] else "passed",
                   "detail": ("；".join(trace["untraced"]) if trace["untraced"] else f"{trace['checked']} 个数字都能追回证据账")[:500]
                   + (f"；放行：{'、'.join(a.allow)}" if a.allow else "")})
    for c in checks:
        print(f"[{c['result']}] {c['name']}：{c['detail']}")
    if any(c["result"] == "failed" for c in checks):
        print("没有出海报：先按上面的问题修改 HTML 或证据账。")
        return 1
    png = html.with_suffix(".png")
    w, h = SIZES[a.A]
    code, out, err = run([py, str(scripts / "capture.py"), str(html), "--output", str(png), "--width", w, "--height", h])
    if code != 0 or not png.is_file():
        print(f"截图失败：{(out + err)[-300:]}", file=sys.stderr)
        return 2
    code, out, err = run([py, str(scripts / "project.py"), "record-build", str(d), "--A", a.A, "--B", a.B, "--C", a.C, "--T", a.T,
                          "--E", a.E, "--F", a.F, "--html", str(html), "--png", str(png),
                          "--static-check", str(static), "--render-check", str(render)])
    checks.append({"name": "project record-build", "result": "passed" if code == 0 else "failed", "detail": (out + err).strip()[-300:]})
    code, out, err = run([py, str(scripts / "project.py"), "validate", str(d), "--require-sources"])
    checks.append({"name": "project validate --require-sources", "result": "passed" if code == 0 else "failed", "detail": (out + err).strip()[-300:]})
    if any(c["result"] == "failed" for c in checks[-2:]):
        for c in checks[-2:]:
            print(f"[{c['result']}] {c['name']}：{c['detail']}")
        return 1
    out_dir = task / "08_deliverables" / "poster"
    out_dir.mkdir(parents=True, exist_ok=True)
    files = []
    for f in (html, png):
        dest = out_dir / f.name
        shutil.copy2(f, dest)
        files.append(str(dest.relative_to(task)))
    title = a.title or json.loads((d / "onepager.ir.json").read_text(encoding="utf-8"))["project"]["title"]
    entry = Acceptance(task).record({"id": f"poster-{a.slug}", "kind": "poster", "title": title, "files": files,
                                     "upstream_checks": checks, "number_trace": {"checked": trace["checked"], "untraced": trace["untraced"]}})
    print(f"已出海报：{out_dir / png.name}")
    print(f"验收状态：{entry['status']}（还需成品审查员看图后用 tools/acceptance.py review poster-{a.slug} 写入结论）")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="出一页海报")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("prepare")
    p.add_argument("task")
    p.add_argument("--slug", required=True)
    p.add_argument("--title", required=True)
    p.add_argument("--claims", help="只用这些主张，逗号分隔；默认用全部能进成品的主张")
    f = sub.add_parser("finish")
    f.add_argument("task")
    f.add_argument("--slug", required=True)
    f.add_argument("--html", required=True)
    f.add_argument("--title")
    for k in ("A", "B", "C", "T", "E"):
        f.add_argument(f"--{k}", required=True)
    f.add_argument("--F", required=True, help="署名，或“无”")
    f.add_argument("--allow", action="append", default=[], help="显式放行的数字（会写进验收记录）")
    a = ap.parse_args(argv)
    return prepare(a) if a.cmd == "prepare" else finish(a)


if __name__ == "__main__":
    sys.exit(main())
