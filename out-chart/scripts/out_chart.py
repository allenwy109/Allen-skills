#!/usr/bin/env python3
"""出图表：转换 → 引擎校验 → 渲染 → 登记验收（设计 §6.2 out-chart）。

用法：
  python3 out_chart.py <任务文件夹> <图表 spec...> --name <交付物名> [--title 标题] [--theme 配色] [--force]
图表 spec 一般放在 07_storyline/charts/*.json（格式见 tools/bridge/MAPPING.md）。
产物：08_deliverables/charts/<名>.pptx、<名>.html、png/<图表 id>.png；验收条目 chart-<名>。
--force 只在 tc_validate 判为"不能做"、且用户明确接受折中时使用（图注必须写明折中内容）。
渲染完成后还要由成品审查员看图，用 tools/acceptance.py review 写入结论，之后才能算完成。
退出码：0 已渲染；1 被转换或校验拦下（没有渲染）；2 参数或环境错误。
"""
import argparse
import json
import os
import pathlib
import subprocess
import sys

SKILL_DIR = pathlib.Path(__file__).resolve().parents[1]


def _bootstrap():
    for c in (os.environ.get("ALLEN_RUNTIME"), SKILL_DIR.parent / "_allen-runtime", SKILL_DIR.parent):
        if c and (pathlib.Path(c) / "tools" / "lib" / "runtime.py").is_file():
            sys.path.insert(0, str(pathlib.Path(c)))
            return pathlib.Path(c)
    raise SystemExit("找不到运行时（tools/lib），请先运行 ./install.sh")


RT_HINT = _bootstrap()
from tools.acceptance import Acceptance  # noqa: E402
from tools.bridge.to_thinkcell import BridgeError, build  # noqa: E402
from tools.lib import runtime  # noqa: E402


def validate(py, engine, specs):
    p = subprocess.run([py, str(engine / "scripts" / "tc_validate.py"), *map(str, specs), "--json"],
                       capture_output=True, text=True, cwd=engine)
    try:
        return json.loads(p.stdout)
    except ValueError:
        raise SystemExit(f"tc_validate 输出无法解析：{(p.stdout + p.stderr)[-300:]}")


def main(argv=None):
    ap = argparse.ArgumentParser(description="出可编辑图表（PPTX、PNG、HTML）")
    ap.add_argument("task")
    ap.add_argument("charts", nargs="+")
    ap.add_argument("--name", required=True, help="交付物名，只用小写字母、数字和连字符")
    ap.add_argument("--title", help="验收记录里的标题，默认取第一张图的标题")
    ap.add_argument("--theme")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args(argv)
    task = pathlib.Path(a.task)
    engine = runtime.engine_dir("thinkcell-charts", skill_dir=SKILL_DIR)
    py = str(runtime.venv_python())
    build_dir = task / "07_storyline" / "charts" / ".build"
    build_dir.mkdir(parents=True, exist_ok=True)

    built, trace, bridge_problems, titles = [], {"checked": 0, "untraced": []}, [], []
    for c in a.charts:
        chart = json.loads(pathlib.Path(c).read_text(encoding="utf-8"))
        titles.append(chart.get("title", ""))
        try:
            spec, t = build(task, chart)
        except BridgeError as err:
            bridge_problems += [f"{pathlib.Path(c).name}：{p}" for p in err.problems]
            continue
        out = build_dir / pathlib.Path(c).name
        out.write_text(json.dumps(spec, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        built.append(out)
        trace["checked"] += t["checked"]
        trace["untraced"] += t["untraced"]

    checks = [{"name": "转换（to_thinkcell）", "result": "failed" if bridge_problems else "passed",
               "detail": "；".join(bridge_problems)[:500] if bridge_problems else f"{trace['checked']} 个数字全部取自证据账"}]
    results = validate(py, engine, built) if built and not bridge_problems else []
    # tc_validate 的致命问题级别是 fatal，整体结论是"不能做"；两者任一出现都按"不能做"处理
    fails = [f"{r.get('id') or r['type']}：{i['msg']}" for r in results for i in r["issues"] if i["level"] == "fatal"]
    fails += [f"{r.get('id') or r['type']}：结论为不能做" for r in results
              if r.get("status") == "不能做" and not any(i["level"] == "fatal" for i in r["issues"])]
    warns = [f"{r.get('id') or r['type']}：{i['msg']}" for r in results for i in r["issues"] if i["level"] == "warn"]
    if results:
        if fails and not a.force:
            checks.append({"name": "tc_validate", "result": "failed", "detail": "；".join(fails)[:500]})
        elif fails or warns:
            detail = ("已按用户接受的折中强制渲染：" if fails else "") + "；".join(fails + warns)
            checks.append({"name": "tc_validate", "result": "warnings", "detail": detail[:500]})
        else:
            checks.append({"name": "tc_validate", "result": "passed", "detail": "全部能做"})
    blocked = any(c["result"] == "failed" for c in checks)
    for c in checks:
        print(f"[{c['result']}] {c['name']}：{c.get('detail', '')}")
    if blocked:
        print("没有渲染：先按上面的问题修改图表 spec 或证据账。")
        return 1

    out_dir = task / "08_deliverables" / "charts"
    out_dir.mkdir(parents=True, exist_ok=True)
    pptx, html, png_dir = out_dir / f"{a.name}.pptx", out_dir / f"{a.name}.html", out_dir / "png"
    env = dict(os.environ, PATH=f"{RT_HINT / 'tools' / 'bin'}{os.pathsep}{os.environ.get('PATH', '')}")
    cmd = [py, str(engine / "scripts" / "tc_render.py"), *map(str, built), "-o", str(pptx), "--png", str(png_dir), "--html", str(html)]
    if a.theme:
        cmd += ["--theme", a.theme]
    if a.force:
        cmd.append("--force")
    p = subprocess.run(cmd, capture_output=True, text=True, cwd=engine, env=env)
    pngs = sorted(l.split("PNG:", 1)[1].strip() for l in p.stdout.splitlines() if l.startswith("PNG:"))
    if p.returncode != 0 or not pptx.is_file() or not html.is_file() or len(pngs) != len(built):
        print(f"渲染失败：{(p.stdout + p.stderr)[-500:]}", file=sys.stderr)
        return 2
    files = [str(f.relative_to(task)) for f in [pptx, html, *map(pathlib.Path, pngs)]]
    entry = Acceptance(task).record({"id": f"chart-{a.name}", "kind": "chart", "title": a.title or titles[0],
                                     "files": files, "upstream_checks": checks, "number_trace": trace})
    print(f"已渲染：{pptx}、{html}、{len(pngs)} 张 PNG")
    print(f"验收状态：{entry['status']}（还需成品审查员看图后用 tools/acceptance.py review chart-{a.name} 写入结论）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
