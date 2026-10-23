#!/usr/bin/env python3
"""完成报告引擎的能力探测验证，并记录结果（设计 §9）。

前提：已运行 ./install.sh --render-deps，生成了 <运行时>/.probe-task/。
做法：由 Claude Code 或 Codex 在会话里实际打开 <运行时>/.probe-task/vision-challenge.png，按引擎要求写 response.json：
  {"code":"图中六字符","shape_left_to_right":["颜色 形状","颜色 形状","颜色 形状"]}
不能读取答案文件代替看图。然后运行：
  python3 tools/record_probe.py --response <response.json>
结果写入 <运行时>/.probe.json，doctor 据此判断是否已验证。退出码：0 通过；1 未通过；2 参数错误。
"""
import argparse
import json
import pathlib
import subprocess
import sys
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from tools.lib import runtime  # noqa: E402


def run(rt, response, runner=subprocess.run, now=None):
    rt, response = pathlib.Path(rt), pathlib.Path(response)
    if not response.is_file():
        print(f"错误：找不到 {response}", file=sys.stderr)
        return 2
    forge = runtime.engine_path(rt, "report-forge")
    try:
        p = runner(["node", "scripts/probe_capabilities.cjs", str(rt / ".probe-task"), "--verify", str(response)],
                   cwd=forge, capture_output=True, text=True)
    except OSError as err:
        print(f"错误：无法运行 node：{err}", file=sys.stderr)
        return 2
    output = (p.stdout or "") + (p.stderr or "")
    lock = json.loads((rt / "vendor" / "vendor.lock").read_text(encoding="utf-8"))
    record = {
        "verified": p.returncode == 0,
        "commit": lock.get("commit"),
        "at": now or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "output_tail": output[-500:],
    }
    (rt / ".probe.json").write_text(json.dumps(record, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(output.strip())
    print("能力探测验证通过" if record["verified"] else "能力探测验证没有通过")
    return 0 if record["verified"] else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description="完成报告引擎能力探测的看图验证并记录结果")
    ap.add_argument("--response", required=True, help="看图后写好的 response.json")
    a = ap.parse_args(argv)
    try:
        rt = runtime.runtime_root()
    except runtime.RuntimeNotFound as err:
        print(f"错误：{err}", file=sys.stderr)
        return 2
    return run(rt, a.response)


if __name__ == "__main__":
    sys.exit(main())
