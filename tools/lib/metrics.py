"""指标取值与"能否进成品"的判断（设计 §3.4、§6.2、§8.3）。

- 公式算法与报告引擎（report-forge content_contract）一致：
  sum、multiply 对全部参数；subtract、divide 用前两个；percent_change =（本期/基期 − 1）× 100，基期须为正；
  share = 部分/总量 × 100；分母为 0 报错。
- 显示时用十进制半入（中点远离零），并消除负零。
- 一个指标能进成品，必须同时满足：被至少一条主张引用（可追溯）；状态不是 missing 或 not_applicable；
  引用它的主张里至少有一条可以呈现（verified、single_source，或 conflicting 且冲突已处理）。
"""
from decimal import ROUND_HALF_UP, Decimal


class MetricError(Exception):
    pass


PRESENTABLE = {"verified", "single_source"}


def evaluate(metrics, mid, _visiting=None):
    """返回指标的数值（未舍入）。metrics 是 {id: 记录}。"""
    visiting = _visiting if _visiting is not None else set()
    if mid not in metrics:
        raise MetricError(f"指标 {mid} 不存在")
    m = metrics[mid]
    if m.get("status") in ("missing", "not_applicable"):
        raise MetricError(f"指标 {mid} 的状态是 {m.get('status')}，没有可用的值（缺失不是 0）")
    if mid in visiting:
        raise MetricError(f"指标 {mid} 的公式存在循环引用")
    if m.get("value") is not None:
        return float(m["value"])
    formula = m.get("formula")
    if not formula:
        raise MetricError(f"指标 {mid} 既没有 value 也没有 formula")
    visiting.add(mid)
    values = [evaluate(metrics, a, visiting) for a in formula["args"]]
    visiting.discard(mid)
    op = formula["op"]
    if op in ("divide", "share", "percent_change") and (len(values) < 2 or values[1] == 0):
        raise MetricError(f"指标 {mid} 零除：分母为 0")
    if op == "percent_change" and values[1] < 0:
        raise MetricError(f"指标 {mid} 的 percent_change 基期须为正数")
    if op == "sum":
        return sum(values)
    if op == "multiply":
        out = 1.0
        for v in values:
            out *= v
        return out
    if op == "subtract":
        return values[0] - values[1]
    if op == "divide":
        return values[0] / values[1]
    if op == "percent_change":
        return (values[0] / values[1] - 1) * 100
    if op == "share":
        return values[0] / values[1] * 100
    raise MetricError(f"指标 {mid} 使用了未知运算 {op}")


def display(value, decimals):
    """十进制半入后的显示文本，例如 0.725 → '0.73'（decimals=2）；不出现 -0。"""
    q = Decimal(1).scaleb(-decimals)
    d = Decimal(repr(value)).quantize(q, rounding=ROUND_HALF_UP)
    if d == 0:
        d = abs(d)
    return f"{d:.{decimals}f}"


def claims_by_metric(claims):
    out = {}
    for c in claims:
        for mid in c.get("metric_refs") or []:
            out.setdefault(mid, []).append(c)
    return out


def resolved_conflict_claims(conflicts):
    return {cid for x in conflicts if x.get("status") == "resolved" for cid in x.get("claim_ids") or []}


def presentable(claim, resolved):
    v = claim.get("verification")
    return v in PRESENTABLE or (v == "conflicting" and claim.get("id") in resolved)


def check_presentable(mid, metrics, by_metric, resolved):
    """返回不能进成品的原因列表；空列表表示可以。"""
    reasons = []
    if mid not in metrics:
        return [f"指标 {mid} 不存在"]
    if metrics[mid].get("status") in ("missing", "not_applicable"):
        reasons.append(f"指标 {mid} 的状态是 {metrics[mid]['status']}，不能画进成品")
    users = by_metric.get(mid, [])
    if not users:
        reasons.append(f"指标 {mid} 没有被任何主张引用，无法追溯")
    elif not any(presentable(c, resolved) for c in users):
        states = "、".join(f"{c['id']}={c.get('verification')}" for c in users)
        reasons.append(f"指标 {mid} 所属的主张都不能以事实呈现（{states}）")
    return reasons
