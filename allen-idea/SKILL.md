---
name: allen-idea
description: 评估尚未注册企业、没有完整 BP 的创业想法或技术。用户希望先澄清想法，再比较多种产品、客户或商业模式落地路径，验证真实痛点、需求强度、竞品和未来发展前景时使用。已有明确经营主体且要评估实际经营时使用 allen-company，不使用本入口。
---

# 创业点子与技术企业化前景评估

先完整读取 `references/system-prompt.md`。应用 ID 固定为 `allen-idea`，主场景固定为 `../scene-idea/`，不得重新交给 router 猜场景。

## 启动与控制

L2、L3 必须使用 `<运行时>/tools/app_runtime.py`。先通过多轮提问生成并让用户确认 `00_idea-definition.md`；再生成并确认 `00_venture-paths.md`。确认前调用 `wait`，不得提前研究或写报告。

## 强制覆盖

- 并列比较 2–3 条实质不同的企业化路径；确实只有一条时说明原因；
- 验证真实痛点、需求频率、严重性、紧迫性、现有投入和预算信号；
- 搜索直接竞品、间接竞品、现状替代、邻近进入者和潜在新进入者；
- 分别判断 0–2、3–5、5–10 年前景；
- 区分窗口型快钱、现金流生意、长期复利型、高风险规模赌注和伪机会；
- 给出值得推进、有条件推进、建议调整方向或暂不建议，以及最小验证实验。

## 后台能力

- 研究与核实：`../core-research/`、`../core-evidence/`
- 拆问题与选方法：`../core-framing/`、`../core-method-select/`、`../lib-consulting/`
- 审查、综合、故事线：`../core-review/`、`../core-synthesis/`、`../core-storyline/`
- 正式报告：`../out-report/`

## 证据边界

严格区分用户确认、系统假设、外部事实和推演。讨论热度、搜索量和市场规模不能单独证明需求或付费意愿；没有访谈、订单、采购或持续付费证据时，不得声称付费意愿已验证。

## 交付

L2、L3 交付 HTML + PDF 主报告和 `supporting-package.zip`，二者登记进 `acceptance.json` 并接受成品审查。
