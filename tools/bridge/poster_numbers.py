#!/usr/bin/env python3
"""海报的数字回查（设计 §6.2 out-poster 第 9 步、§8.3 第 1 项）。

onepager 的 HTML 由模型照模板手写，转换脚本拦不住手写阶段新冒出来的数字，所以成品出来后再查一遍：
- 抽出页面上所有可见文字里的数字（去掉 style、script、注释和标签；来源编号 M001、主张编号 cl-0001 这类不算数字）；
- 每个数字都必须等于某个"能进成品"的指标的显示值（见 tools/lib/metrics.py），千分位逗号不影响比较；
- 4 位整数 1900–2100 视为年份，不当作数据；另外可以用 allow 显式放行个别数字（例如"3 个阶段"），放行要写进验收记录；
- 指标所属主张是估算、预测等非事实身份时，这个数字前后 20 个字之内必须注明身份（估算、预测、假设、判断、建议、约）；
- BigNumber 的大数字（上游模板里 class 为 bignum-value 的元素）只能用所属主张为 verified 或 single_source 的指标；
  BigNumber 里的标签（bignum-label）按普通文字处理。

用法：python3 tools/bridge/poster_numbers.py <任务文件夹> <海报.html> [--allow 3 --allow 18]
输出 JSON：{checked, untraced, years}；有追溯不到的数字时以 1 退出。
"""
import argparse
import html
import json
import pathlib
import re
import sys
from html.parser import HTMLParser

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from tools.lib import metrics as M  # noqa: E402
from tools.lib.ledger import Ledger  # noqa: E402

ID_PATTERN = re.compile(r"\b(?:[A-Z]\d{3,4}|cl-\d{4,}|m-\d{4,}|ev-\d{4,}|card-\d{4,}|RV-\d{4,})\b")
NUMBER = re.compile(r"(?<![\w.])-?\d[\d,]*(?:\.\d+)?")
IDENTITY_WORDS = ("估算", "预测", "假设", "判断", "建议", "约", "预计")
BIGNUM_KINDS = {"verified", "single_source"}


class _Text(HTMLParser):
    """收集可见文字，并标记哪些片段是 BigNumber 的大数字（class 含 bignum-value）。"""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self.stack, self.skip = [], [], 0

    def handle_starttag(self, tag, attrs):
        if tag in ("style", "script", "template"):
            self.skip += 1
        cls = dict(attrs).get("class") or ""
        if tag not in ("br", "img", "meta", "link", "hr", "input"):
            self.stack.append("bignum-value" in cls.split())

    def handle_endtag(self, tag):
        if tag in ("style", "script", "template"):
            self.skip = max(0, self.skip - 1)
        if tag not in ("br", "img", "meta", "link", "hr", "input") and self.stack:
            self.stack.pop()

    def handle_data(self, data):
        if not self.skip and data.strip():
            self.parts.append((data, any(self.stack)))


def visible_parts(text):
    p = _Text()
    p.feed(text)
    return [(html.unescape(t), big) for t, big in p.parts]


def presentable_values(task):
    """返回 {显示值: [(指标ID, 主张身份集合, 能否用于 BigNumber)]}。"""
    led = Ledger(task)
    metrics = {m["id"]: m for m in led.read("metrics")}
    claims = led.read("claims")
    by_metric = M.claims_by_metric(claims)
    resolved = M.resolved_conflict_claims(led.read("conflicts"))
    out = {}
    for mid, m in metrics.items():
        if M.check_presentable(mid, metrics, by_metric, resolved):
            continue
        try:
            shown = M.display(M.evaluate(metrics, mid), m["decimals"])
        except M.MetricError:
            continue
        users = by_metric.get(mid, [])
        kinds = {c["kind"] for c in users}
        big = any(c.get("verification") in BIGNUM_KINDS for c in users)
        out.setdefault(shown, []).append((mid, kinds, big))
    return out


def check(task, html_text, allow=()):
    values = presentable_values(task)
    allow = {a.replace(",", "") for a in allow}
    checked, untraced, years = 0, [], []
    for text, in_bignum in visible_parts(html_text):
        clean = ID_PATTERN.sub(" ", text)
        for m in NUMBER.finditer(clean):
            raw = m.group(0)
            num = raw.replace(",", "")
            if num.lstrip("-") == "":
                continue
            if re.fullmatch(r"(19|20|21)\d\d", num) and not in_bignum:
                years.append(num)
                continue
            checked += 1
            if num in allow:
                continue
            hits = values.get(num)
            where = f"“{text.strip()[:30]}”里的 {raw}"
            if not hits:
                untraced.append(f"{where}：不是任何能进成品的指标的显示值")
                continue
            if in_bignum and not any(big for _, _, big in hits):
                untraced.append(f"{where}：BigNumber 只能用已核实或单一来源主张的指标")
                continue
            non_fact = all(k not in ("fact", "data") for _, kinds, _ in hits for k in kinds)
            if non_fact:
                window = clean[max(0, m.start() - 20): m.end() + 20]
                if not any(w in window for w in IDENTITY_WORDS):
                    untraced.append(f"{where}：这是估算或预测类数值，前后 20 字内要注明身份")
    return {"checked": checked, "untraced": untraced, "years": sorted(set(years))}


def main(argv=None):
    ap = argparse.ArgumentParser(description="海报数字回查")
    ap.add_argument("task")
    ap.add_argument("html")
    ap.add_argument("--allow", action="append", default=[], help="显式放行的数字（要写进验收记录）")
    a = ap.parse_args(argv)
    result = check(a.task, pathlib.Path(a.html).read_text(encoding="utf-8"), a.allow)
    print(json.dumps(result, ensure_ascii=False, indent=1))
    return 1 if result["untraced"] else 0


if __name__ == "__main__":
    sys.exit(main())
