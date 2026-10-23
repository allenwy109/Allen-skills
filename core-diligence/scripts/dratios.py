"""财务比率（能力清单 H 节 financial_ratios.py 的规则，L 节优化 6）。只用标准库。

保守设计：缺输入 → missing（不补 0）；分母 ≤ 0 → not_applicable；用了期末余额或代理分母 → approximate（必须显式允许）；
每个非空输入都要有证据；阈值触发只是核查线索。比率按小数输出（0.25 表示 25%），天数和月数按原单位。

新增（优化 6）：营业利润率、EBITDA 与 EBITDA 利润率、资产负债率、净债务/EBITDA、利息覆盖、投入资本回报（ROIC）、
年化 ROA/ROE（单独列出，原口径不年化）、多期序列的同比与环比、TTM 收入、收入结构占比。
"""
import datetime
import math

SCOPES = ("consolidated", "standalone", "segment")
ATTRIBUTES = ("actual", "forecast", "estimate")
REQUIRED = ("entity_id", "scope", "period_start", "period_end", "days", "currency", "unit", "accounting_basis", "attribute", "audited",
            "source_ids", "values", "input_evidence")
VALUES = ("revenue", "cost", "net_profit", "operating_profit", "depreciation", "amortization", "interest_expense", "income_tax",
          "profit_before_tax", "operating_cashflow", "current_assets", "current_liabilities", "inventory", "prepayments",
          "assets_begin", "assets_end", "equity_begin", "equity_end", "receivables_begin", "receivables_end", "inventory_begin",
          "inventory_end", "payables_begin", "payables_end", "invested_capital_begin", "invested_capital_end", "credit_sales", "purchases",
          "capex", "available_cash", "cash_and_equivalents", "monthly_net_burn", "total_debt", "total_assets")
OPTIONS = {"allow_end_balance": False, "allow_revenue_proxy": False, "allow_cost_proxy": False, "quick_deductions": ["inventory", "prepayments"],
           "near_zero_profit": 0.01, "capex_sign": "positive_outflow"}
BURN_FLAGS = ("cash_excludes_restricted", "includes_capex", "includes_debt_service", "includes_committed_spend")


class InputError(Exception):
    pass


def _date(s):
    return datetime.date.fromisoformat(s)


def validate_period(p, where):
    for k in REQUIRED:
        if k not in p or p[k] in (None, "") and k not in ("audited",):
            raise InputError(f"{where}：缺少口径字段 {k}")
    if p["scope"] not in SCOPES:
        raise InputError(f"{where}：scope 只能是 {'/'.join(SCOPES)}")
    if p["attribute"] not in ATTRIBUTES:
        raise InputError(f"{where}：attribute 只能是 {'/'.join(ATTRIBUTES)}")
    days = (_date(p["period_end"]) - _date(p["period_start"])).days + 1
    if not isinstance(p["days"], int) or p["days"] != days or days <= 0:
        raise InputError(f"{where}：days 必须等于结束日减开始日加 1（{days}）")
    unknown = set(p["values"]) - set(VALUES)
    if unknown:
        raise InputError(f"{where}：values 里有不认识的字段 {sorted(unknown)}")
    for k, v in p["values"].items():
        if v is None:
            continue
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
            raise InputError(f"{where}：{k} 必须是有限数")
        if not p["input_evidence"].get(k):
            raise InputError(f"{where}：{k} 有值但 input_evidence 没有证据")


class Calc:
    def __init__(self, period, options, evidence_key="input_evidence"):
        self.p, self.v, self.o = period, period["values"], options
        self.out = {}

    def ev(self, *keys):
        return sorted({e for k in keys for e in self.p["input_evidence"].get(k) or []})

    def put(self, name, value=None, status="ok", formula="", inputs=(), reason="", attribute=None):
        if value is not None and not math.isfinite(value):
            value, status, reason = None, "not_applicable", reason or "结果不是有限数"
        self.out[name] = {"value": value, "status": status, "formula": formula, "inputs": list(inputs), "evidence_ids": self.ev(*inputs),
                          "reason": reason, "attribute": attribute or self.p["attribute"], "applicability": self.p["scope"]}

    def get(self, *keys):
        missing = [k for k in keys if self.v.get(k) is None]
        return None if missing else [self.v[k] for k in keys]

    def ratio(self, name, num_keys, den_key, formula, numerator=None):
        vals = self.get(*num_keys, den_key)
        if vals is None:
            return self.put(name, status="missing", formula=formula, inputs=(*num_keys, den_key), reason="输入缺失，不补 0")
        den = vals[-1]
        if den <= 0:
            return self.put(name, status="not_applicable", formula=formula, inputs=(*num_keys, den_key), reason="分母 ≤ 0")
        num = numerator(*vals[:-1]) if numerator else vals[0]
        self.put(name, num / den, formula=formula, inputs=(*num_keys, den_key))

    def average(self, base):
        b, e = self.v.get(f"{base}_begin"), self.v.get(f"{base}_end")
        if b is not None and e is not None:
            return (b + e) / 2, False, (f"{base}_begin", f"{base}_end")
        if e is not None and self.o["allow_end_balance"]:
            return e, True, (f"{base}_end",)
        return None, False, (f"{base}_begin", f"{base}_end")


def calculate(doc):
    """返回 {"metrics": {名称: 结果}, "alerts": [...], "series": [...], "segments": {...}}；输入不合规抛 InputError。"""
    unknown = set(doc.get("options") or {}) - set(OPTIONS)
    if unknown:
        raise InputError(f"不认识的 options：{sorted(unknown)}")
    o = {**OPTIONS, **(doc.get("options") or {})}
    qd = o["quick_deductions"]
    if not qd or len(set(qd)) != len(qd) or not set(qd) <= {"inventory", "prepayments"}:
        raise InputError("quick_deductions 只能是 inventory、prepayments 的非空不重复子集")
    if o["near_zero_profit"] < 0:
        raise InputError("near_zero_profit 不能为负")
    validate_period(doc, "本期")
    c = Calc(doc, o)
    v = doc["values"]
    c.ratio("gross_margin", ("revenue", "cost"), "revenue", "(revenue − cost) / revenue", lambda r, k: r - k)
    c.ratio("net_margin", ("net_profit",), "revenue", "net_profit / revenue")
    c.ratio("operating_margin", ("operating_profit",), "revenue", "operating_profit / revenue")
    ebitda_in = c.get("operating_profit", "depreciation", "amortization")
    if ebitda_in is None:
        c.put("ebitda", status="missing", formula="operating_profit + depreciation + amortization",
              inputs=("operating_profit", "depreciation", "amortization"), reason="输入缺失")
    else:
        c.put("ebitda", sum(ebitda_in), formula="operating_profit + depreciation + amortization", inputs=("operating_profit", "depreciation", "amortization"))
    if c.out["ebitda"]["status"] == "ok" and v.get("revenue") is not None:
        if v["revenue"] > 0:
            c.put("ebitda_margin", c.out["ebitda"]["value"] / v["revenue"], formula="ebitda / revenue",
                  inputs=("operating_profit", "depreciation", "amortization", "revenue"))
        else:
            c.put("ebitda_margin", status="not_applicable", formula="ebitda / revenue", inputs=("revenue",), reason="分母 ≤ 0")
    else:
        c.put("ebitda_margin", status="missing", formula="ebitda / revenue", inputs=("revenue",), reason="EBITDA 或收入缺失")
    c.ratio("current_ratio", ("current_assets",), "current_liabilities", "current_assets / current_liabilities")
    q = c.get("current_assets", "current_liabilities", *qd)
    if q is None:
        c.put("quick_ratio", status="missing", formula="(current_assets − Σ扣除项) / current_liabilities", inputs=("current_assets", "current_liabilities", *qd),
              reason="任一扣除项缺失则整项缺失")
    elif q[1] <= 0:
        c.put("quick_ratio", status="not_applicable", formula="(current_assets − Σ扣除项) / current_liabilities", inputs=("current_liabilities",), reason="分母 ≤ 0")
    else:
        c.put("quick_ratio", (q[0] - sum(q[2:])) / q[1], formula="(current_assets − Σ扣除项) / current_liabilities", inputs=("current_assets", "current_liabilities", *qd))
    for name, base in (("roa", "assets"), ("roe", "equity")):
        avg, approx, keys = c.average(base)
        np_ = v.get("net_profit")
        if avg is None or np_ is None:
            c.put(name, status="missing", formula=f"net_profit / 平均{base}（不年化）", inputs=("net_profit", *keys), reason="输入缺失")
            c.put(f"{name}_annualized", status="missing", formula=f"{name} × 365 / days", inputs=("net_profit", *keys), reason="输入缺失")
        elif avg <= 0:
            c.put(name, status="not_applicable", formula=f"net_profit / 平均{base}", inputs=("net_profit", *keys), reason="分母 ≤ 0")
            c.put(f"{name}_annualized", status="not_applicable", formula=f"{name} × 365 / days", inputs=keys, reason="分母 ≤ 0")
        else:
            st = "approximate" if approx else "ok"
            reason = "用期末余额近似平均余额" if approx else ""
            c.put(name, np_ / avg, st, f"net_profit / 平均{base}（不年化）", ("net_profit", *keys), reason)
            c.put(f"{name}_annualized", np_ / avg * 365 / doc["days"], st, f"{name} × 365 / days（年化，便于跨期比较）", ("net_profit", *keys), reason)
    days = doc["days"]

    def turnover(name, base, flow_key, proxy_key, proxy_flag):
        avg, approx, keys = c.average(base)
        flow, used = v.get(flow_key), flow_key
        if flow is None and o[proxy_flag] and v.get(proxy_key) is not None:
            flow, used, approx = v[proxy_key], proxy_key, True
        formula = f"平均{base} / {flow_key} × days"
        if avg is None or flow is None:
            return c.put(name, status="missing", formula=formula, inputs=(*keys, flow_key), reason="输入缺失")
        if flow <= 0:
            return c.put(name, status="not_applicable", formula=formula, inputs=(*keys, used), reason="分母 ≤ 0")
        c.put(name, avg / flow * days, "approximate" if approx else "ok", formula, (*keys, used),
              "使用了期末余额或代理分母" if approx else "")

    turnover("receivable_days", "receivables", "credit_sales", "revenue", "allow_revenue_proxy")
    turnover("inventory_days", "inventory", "cost", "cost", "allow_cost_proxy")
    turnover("payable_days", "payables", "purchases", "cost", "allow_cost_proxy")
    parts = [c.out[k] for k in ("receivable_days", "inventory_days", "payable_days")]
    if any(x["status"] in ("missing", "not_applicable") for x in parts):
        c.put("cash_conversion_cycle", status="missing", formula="应收天数 + 存货天数 − 应付天数", reason="任一子项缺失或不适用")
    else:
        c.put("cash_conversion_cycle", parts[0]["value"] + parts[1]["value"] - parts[2]["value"],
              "approximate" if any(x["status"] == "approximate" for x in parts) else "ok", "应收天数 + 存货天数 − 应付天数",
              sorted({i for x in parts for i in x["inputs"]}))
    cp = c.get("operating_cashflow", "net_profit")
    if cp is None:
        c.put("cash_profit_ratio", status="missing", formula="operating_cashflow / net_profit", inputs=("operating_cashflow", "net_profit"), reason="输入缺失")
    elif cp[1] <= o["near_zero_profit"]:
        c.put("cash_profit_ratio", status="not_applicable", formula="operating_cashflow / net_profit", inputs=("operating_cashflow", "net_profit"),
              reason="净利润接近 0 或为负，比值没有意义")
    else:
        c.put("cash_profit_ratio", cp[0] / cp[1], formula="operating_cashflow / net_profit", inputs=("operating_cashflow", "net_profit"))
    fcf = c.get("operating_cashflow", "capex")
    if fcf is None:
        c.put("simplified_fcf", status="missing", formula="operating_cashflow − |capex|（不是 FCFF/FCFE）", inputs=("operating_cashflow", "capex"), reason="输入缺失")
    else:
        if (o["capex_sign"] == "positive_outflow" and fcf[1] < 0) or (o["capex_sign"] == "negative_outflow" and fcf[1] > 0):
            raise InputError(f"capex={fcf[1]} 的正负号与声明的 capex_sign={o['capex_sign']} 不一致")
        c.put("simplified_fcf", fcf[0] - abs(fcf[1]), formula="operating_cashflow − |capex|（不是 FCFF/FCFE）", inputs=("operating_cashflow", "capex"))
    basis = doc.get("cash_burn_basis") or {}
    run = c.get("available_cash", "monthly_net_burn")
    if run is not None and run[0] < 0:
        raise InputError("available_cash 不能为负")
    if run is not None and any(not isinstance(basis.get(k), bool) for k in BURN_FLAGS):
        raise InputError("cash_burn_basis 的四个口径（是否剔除受限现金、是否含资本开支、是否含偿债、是否含已承诺支出）都要明确写 true/false")
    if run is None:
        c.put("cash_runway_months", status="missing", formula="available_cash / monthly_net_burn", inputs=("available_cash", "monthly_net_burn"), reason="输入缺失",
              attribute="estimate")
    elif not basis.get("basis") or not basis.get("cash_excludes_restricted"):
        c.put("cash_runway_months", status="missing", formula="available_cash / monthly_net_burn", inputs=("available_cash", "monthly_net_burn"),
              reason="消耗口径没写，或可用现金没有剔除受限现金", attribute="estimate")
    elif run[1] <= 0:
        c.put("cash_runway_months", status="not_applicable", formula="available_cash / monthly_net_burn", inputs=("available_cash", "monthly_net_burn"),
              reason="当前没有净消耗，不代表永久安全", attribute="estimate")
    else:
        c.put("cash_runway_months", run[0] / run[1], formula="available_cash / monthly_net_burn", inputs=("available_cash", "monthly_net_burn"),
              reason=basis.get("limitations") or "", attribute="estimate")
    c.ratio("debt_to_assets", ("total_debt",), "total_assets", "total_debt / total_assets")
    nd = c.get("total_debt", "cash_and_equivalents")
    if nd is None or c.out["ebitda"]["status"] != "ok":
        c.put("net_debt_to_ebitda", status="missing", formula="(total_debt − cash_and_equivalents) / ebitda",
              inputs=("total_debt", "cash_and_equivalents", "operating_profit", "depreciation", "amortization"), reason="输入缺失")
    elif c.out["ebitda"]["value"] <= 0:
        c.put("net_debt_to_ebitda", status="not_applicable", formula="(total_debt − cash_and_equivalents) / ebitda", inputs=("total_debt",), reason="EBITDA ≤ 0")
    else:
        c.put("net_debt_to_ebitda", (nd[0] - nd[1]) / c.out["ebitda"]["value"], formula="(total_debt − cash_and_equivalents) / ebitda",
              inputs=("total_debt", "cash_and_equivalents", "operating_profit", "depreciation", "amortization"))
    c.ratio("interest_coverage", ("operating_profit",), "interest_expense", "operating_profit / interest_expense")
    tax = c.get("income_tax", "profit_before_tax")
    ic, approx_ic, ic_keys = c.average("invested_capital")
    if tax is None or ic is None or v.get("operating_profit") is None:
        c.put("roic", status="missing", formula="operating_profit × (1 − income_tax / profit_before_tax) / 平均投入资本",
              inputs=("operating_profit", "income_tax", "profit_before_tax", *ic_keys), reason="输入缺失")
    elif tax[1] <= 0 or ic <= 0:
        c.put("roic", status="not_applicable", formula="operating_profit × (1 − 有效税率) / 平均投入资本", inputs=("profit_before_tax", *ic_keys),
              reason="税前利润 ≤ 0（有效税率无意义）或投入资本 ≤ 0")
    else:
        c.put("roic", v["operating_profit"] * (1 - tax[0] / tax[1]) / ic, "approximate" if approx_ic else "ok",
              "operating_profit × (1 − income_tax / profit_before_tax) / 平均投入资本（不年化）", ("operating_profit", "income_tax", "profit_before_tax", *ic_keys),
              "用期末投入资本近似" if approx_ic else "")
    growth(doc, c)
    alerts = []
    for t in doc.get("thresholds") or []:
        if t.get("metric") not in c.out or t.get("operator") not in ("lt", "gt") or not t.get("scope") or not t.get("source"):
            raise InputError(f"阈值写法不对：{t}")
        m = c.out[t["metric"]]
        if m["value"] is not None and ((t["operator"] == "lt" and m["value"] < t["value"]) or (t["operator"] == "gt" and m["value"] > t["value"])):
            alerts.append({"metric": t["metric"], "value": m["value"], "threshold": t, "note": "只是核查线索，不是结论"})
    return {"metrics": c.out, "alerts": alerts, "series": series(doc), "segments": segments(doc, c)}


def comparable(a, b):
    """同比可比：主体、口径、币种、单位、会计口径相同；天数差 ≤ 1；上期在本期之前；起止月日相同；两期都是实际数。"""
    same = all(a[k] == b[k] for k in ("entity_id", "scope", "currency", "unit", "accounting_basis"))
    return (same and abs(a["days"] - b["days"]) <= 1 and b["period_end"] < a["period_start"]
            and a["period_start"][5:] == b["period_start"][5:] and a["period_end"][5:] == b["period_end"][5:]
            and a["attribute"] == b["attribute"] == "actual")


def growth(doc, c):
    prior = doc.get("prior")
    formula = "revenue / prior.revenue − 1"
    if not prior:
        return c.put("revenue_growth", status="missing", formula=formula, inputs=("revenue",), reason="没有上期数据")
    validate_period(prior, "上期")
    r, pr = doc["values"].get("revenue"), prior["values"].get("revenue")
    if r is None or pr is None:
        return c.put("revenue_growth", status="missing", formula=formula, inputs=("revenue",), reason="收入缺失")
    if not comparable(doc, prior):
        return c.put("revenue_growth", status="not_applicable", formula=formula, inputs=("revenue",), reason="两期口径不可比（主体、范围、币种、单位、会计口径、期间长度或属性不同）")
    if pr <= 0:
        return c.put("revenue_growth", status="not_applicable", formula=formula, inputs=("revenue",), reason="上期收入 ≤ 0")
    c.put("revenue_growth", r / pr - 1, formula=formula, inputs=("revenue",))
    c.out["revenue_growth"]["prior_revenue"] = pr
    c.out["revenue_growth"]["evidence_ids"] = sorted(set(c.out["revenue_growth"]["evidence_ids"]) | set(prior["input_evidence"].get("revenue") or []))


def series(doc):
    """多期序列：按期间排序，逐期给出同比（相隔一年、口径可比）和环比（相邻且等长）；最近 4 个相邻季度齐全时给 TTM 收入。"""
    periods = sorted(doc.get("series") or [], key=lambda p: p["period_start"])
    for i, p in enumerate(periods):
        validate_period(p, f"series[{i}]")
    out = []
    for i, p in enumerate(periods):
        row = {"period_start": p["period_start"], "period_end": p["period_end"], "revenue": p["values"].get("revenue"),
               "yoy": None, "qoq": None, "evidence_ids": p["input_evidence"].get("revenue") or []}
        prev = periods[i - 1] if i else None
        if prev and prev["values"].get("revenue") and p["values"].get("revenue") is not None and abs(prev["days"] - p["days"]) <= 3 \
                and _date(prev["period_end"]) + datetime.timedelta(days=1) == _date(p["period_start"]) and prev["values"]["revenue"] > 0:
            row["qoq"] = p["values"]["revenue"] / prev["values"]["revenue"] - 1
        last_year = next((q for q in periods if comparable(p, q) and q["period_start"][:4] == str(int(p["period_start"][:4]) - 1)), None)
        if last_year and last_year["values"].get("revenue") and p["values"].get("revenue") is not None and last_year["values"]["revenue"] > 0:
            row["yoy"] = p["values"]["revenue"] / last_year["values"]["revenue"] - 1
        out.append(row)
    quarters = [p for p in periods if 89 <= p["days"] <= 92]
    if len(quarters) >= 4:
        last4 = quarters[-4:]
        chained = all(_date(a["period_end"]) + datetime.timedelta(days=1) == _date(b["period_start"]) for a, b in zip(last4, last4[1:]))
        if chained and all(q["values"].get("revenue") is not None for q in last4):
            out.append({"ttm_revenue": sum(q["values"]["revenue"] for q in last4), "period_start": last4[0]["period_start"],
                        "period_end": last4[-1]["period_end"], "evidence_ids": sorted({e for q in last4 for e in q["input_evidence"].get("revenue") or []})})
    return out


def segments(doc, c):
    """收入结构占比：只在分项和总额同口径时计算；分项之和与总额不一致时不补"其他"凑满 100%，而是写出未解释部分。"""
    seg = doc.get("segments") or {}
    total = doc["values"].get("revenue")
    if not seg:
        return {}
    if total is None or total <= 0:
        return {"status": "not_applicable", "reason": "总收入缺失或 ≤ 0"}
    shares = {k: v / total for k, v in seg["values"].items()}
    unexplained = total - sum(seg["values"].values())
    return {"status": "ok", "shares": shares, "unexplained": unexplained, "evidence_ids": seg.get("evidence_ids") or [],
            "note": "分项之和与总收入不一致，未解释部分单独列出，不并入任何分项" if abs(unexplained) > 1e-9 else ""}
