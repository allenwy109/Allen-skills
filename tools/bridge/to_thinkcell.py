#!/usr/bin/env python3
"""把我们的图表 spec（07_storyline/charts/*.json）转成 thinkcell 引擎的输入（设计 §6.2、§6.3；映射见 MAPPING.md）。

我们的 spec 与 thinkcell 的格式相同，只有三点不同：
  1. data 里的每个数（以及 value_line 装饰的 value）都写成指标引用 {"metric": "m-0001"}，由本脚本从证据账取值；
     data 里出现裸数字就拒绝（追溯不到证据账）。版式和格式参数（axis_break、format 等）可以写数字。
  2. 不写 source，改写 source_ids（来源 ID 列表），由本脚本拼成来源说明。
  3. 引用的指标必须能进成品：被主张引用、不是缺失、所属主张可以呈现（见 tools/lib/metrics.py）。
数值按指标的 decimals 做十进制半入后交给引擎，与报告引擎的显示一致。

用法：python3 tools/bridge/to_thinkcell.py <任务文件夹> <图表 spec> -o <输出.json>
退出码：0 成功；1 有不能转换的问题（逐条列出）；2 文件错误。
"""
import argparse
import copy
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from tools.lib import metrics as M  # noqa: E402
from tools.lib.ledger import Ledger  # noqa: E402

NON_DATA_KEYS = {"axis_break", "format", "delta_format", "scale_max", "decimals", "font_size"}
REQUIRED = ("type", "title", "unit", "data", "source_ids")
NOT_FACT_KINDS = {"estimate": "估算", "forecast": "预测", "assumption": "假设", "judgment": "判断", "recommendation": "建议"}


class BridgeError(Exception):
    def __init__(self, problems):
        super().__init__("；".join(problems))
        self.problems = problems


def build(task, chart):
    """返回 (thinkcell spec, 追溯结果 {checked, untraced})；有问题时抛 BridgeError。"""
    led = Ledger(task)
    metrics = {m["id"]: m for m in led.read("metrics")}
    claims = led.read("claims")
    by_metric = M.claims_by_metric(claims)
    resolved = M.resolved_conflict_claims(led.read("conflicts"))
    sources = {s["id"]: s for s in led.read("sources")}
    problems, untraced, used = [], [], []
    for key in REQUIRED:
        if chart.get(key) in (None, "", []):
            problems.append(f"缺少 {key}")
    if "source" in chart:
        problems.append("不要直接写 source，改写 source_ids（来源 ID 列表）")

    def resolve(node, path):
        if isinstance(node, dict) and set(node) == {"metric"}:
            mid = node["metric"]
            used.append(mid)
            reasons = M.check_presentable(mid, metrics, by_metric, resolved)
            if reasons:
                problems.extend(f"{path}：{r}" for r in reasons)
                return None
            try:
                return float(M.display(M.evaluate(metrics, mid), metrics[mid]["decimals"]))
            except M.MetricError as err:
                problems.append(f"{path}：{err}")
                return None
        if isinstance(node, dict):
            return {k: (v if k in NON_DATA_KEYS else resolve(v, f"{path}.{k}")) for k, v in node.items()}
        if isinstance(node, list):
            return [resolve(v, f"{path}[{i}]") for i, v in enumerate(node)]
        if isinstance(node, (int, float)) and not isinstance(node, bool):
            untraced.append(path)
            problems.append(f"{path}：裸数字 {node} 追溯不到证据账，请改写成 {{\"metric\": \"m-…\"}}")
        return node

    spec = copy.deepcopy(chart)
    spec.pop("source_ids", None)
    if "data" in chart:
        spec["data"] = resolve(chart["data"], "data")
    for i, d in enumerate(spec.get("decorations") or []):
        if "value" in d:
            d["value"] = resolve(d["value"], f"decorations[{i}].value")
    missing_src = [s for s in chart.get("source_ids") or [] if s not in sources]
    if missing_src:
        problems.append(f"source_ids 里有不存在的来源：{'、'.join(missing_src)}")
    if problems:
        raise BridgeError(problems)
    spec["source"] = "；".join(f"{sources[s]['title']}（{s}）" for s in chart["source_ids"])
    notes = []
    if any(metrics[m].get("status") == "approximate" for m in used):
        notes.append("部分数值为近似值")
    kinds = {c["kind"] for m in used for c in by_metric.get(m, []) if c["kind"] in NOT_FACT_KINDS}
    if kinds:
        notes.append("含" + "、".join(NOT_FACT_KINDS[k] for k in sorted(kinds)) + "数值，不是实际数据")
    if notes:
        existing = [spec["footnote"]] if spec.get("footnote") else []
        spec["footnote"] = "；".join(existing + notes)
    return spec, {"checked": len(used), "untraced": untraced}


def main(argv=None):
    ap = argparse.ArgumentParser(description="图表 spec → thinkcell 引擎输入")
    ap.add_argument("task")
    ap.add_argument("chart")
    ap.add_argument("-o", "--out", required=True)
    a = ap.parse_args(argv)
    try:
        chart = json.loads(pathlib.Path(a.chart).read_text(encoding="utf-8"))
        spec, trace = build(a.task, chart)
    except BridgeError as err:
        for p in err.problems:
            print(f"不能转换：{p}")
        return 1
    except (OSError, ValueError) as err:
        print(f"错误：{err}", file=sys.stderr)
        return 2
    pathlib.Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    pathlib.Path(a.out).write_text(json.dumps(spec, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({"out": a.out, **trace}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
