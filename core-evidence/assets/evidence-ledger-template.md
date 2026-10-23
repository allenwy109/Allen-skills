# 证据账怎么写

证据账不再用手写表格维护。它是任务文件夹里的 `03_evidence/ledger/`，每张表一个 JSONL 文件，由 `tools/lib/ledger.py` 负责编号、加锁、备份和校验。字段与枚举只在 `tools/lib/schema/ledger.schema.json` 里定义。

## 常用命令

```bash
python3 <运行时>/tools/lib/ledger.py <任务文件夹> init                # 建证据账目录和 project 记录
python3 <运行时>/tools/lib/ledger.py <任务文件夹> next-id sources --line M
python3 <运行时>/tools/lib/ledger.py <任务文件夹> check               # 有错误时以 1 退出
python3 <运行时>/tools/lib/ledger.py <任务文件夹> render              # 生成 ledger.md、notes/、search-logs/
python3 <运行时>/tools/lib/ledger.py <任务文件夹> merge A             # 并入研究线 A 的暂存记录
```

`<运行时>` 是本仓库根目录，或安装后的 `~/.claude/skills/_allen-runtime`（Claude Code）、`~/.codex/skills/_allen-runtime`（Codex）。

## 在 Python 里写入

```python
import sys; sys.path.insert(0, "<运行时>")
from tools.lib.ledger import Ledger

led = Ledger("<任务文件夹>")
src = led.add("sources", {
    "origin": "web", "title": "某公司 2025 年年报", "url": "https://…", "published": "2026-03-28",
    "published_precision": "day", "accessed": "2026-10-22T10:00:00+08:00", "tier": "primary", "grade": "S",
    "capture_method": "browser", "access": "full"}, line="M")          # → "M001"
ev = led.add("evidence", {"source_id": src, "locator": "p12 表 3", "excerpt": "营业收入 1.2 亿元",
                          "attribute": "actual", "numeric": False})        # → "ev-0001"
cl = led.add("claims", {
    "kind": "data", "statement": "2025 年营业收入 1.2 亿元", "scope": "consolidated", "period": "2025 全年",
    "population": "合并报表主体", "unit": "亿元", "denominator": "不适用：单值", "calculation": "不适用：原文数字",
    "inference": "只说明规模，不说明盈利", "limitation": "未经审计复核", "verification": "single_source",
    "confidence": "medium", "confidence_reason": "只有年报一个来源", "affects_conclusion": True, "materiality": "major"})
led.add("claim_evidence", {"claim_id": cl, "evidence_id": ev, "relation": "supports", "applicable_scope": "合并口径"})
```

## 规则

- 不适用的字段不要留空，写明原因，例如 `"denominator": "不适用：单值"`。
- 日期不确定时留空，并把精度写成 `unknown`，不要编日期。
- 缺失的数不是 0：指标缺失时 `status` 写 `missing` 并写原因，不填值。
- 有冲突时，在 `conflicts` 里登记双方的值和口径；处理后写采信理由。
