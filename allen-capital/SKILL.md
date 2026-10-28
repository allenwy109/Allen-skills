---
name: allen-capital
description: 判断一家企业的资本市场对接价值、融资准备度和本公司适合的参与方式。接收 BP、公司简介、融资材料、官网、团队和经营资料；识别真实阶段与轮次，站在投资人角度评估投资价值，同时区分帮助匹配外部资本、有限战略参与、只提供服务或暂不推进。用户提到融资、资本对接、投资价值、跟投或是否值得参与时使用。
---

# 资本市场对接与表现

先完整读取 `references/system-prompt.md`。应用 ID 固定为 `allen-capital`，主场景用 `../scene-company/`，尽调 purpose=`investment`；不要重新交给 router 猜场景。

## 执行要求

L2、L3 用 `<运行时>/tools/app_runtime.py` 控制全流程，后台依次使用 `../core-intake/`、`../core-framing/`、`../core-diligence/`、`../core-evidence/`、`../core-research/`、`../core-method-select/`、`../core-review/`、`../core-synthesis/`、`../core-storyline/` 和 `../out-report/`。

L2、L3 同时遵守 router 第 3.1 节的咨询交付合同；L1 不创建合同文件。

不得因企业声称某轮融资就直接采用该阶段；分别记录声称轮次、根据证据判断的成熟阶段、置信度和冲突。比较后期的项目默认考虑资本匹配，但仍要判断是否值得推荐。公司不是专业基金，自有投资能力有限，不默认建议领投或直接投资。

## 强制输出

- 投资逻辑和最强反对理由；
- 产品竞争力、市场、竞品、商业模式、经营和团队基本面；
- 融资阶段与准备度；
- 适合的资本类型、对接阻碍和补充材料；
- 我方角色建议：资本匹配、有限跟投/联合参与、战略服务、暂缓或不推进；
- 需要进一步核实的事项和尽调问题。

## 交付

一份资本对接与参与判断主报告（PDF + HTML）和一份 `supporting-package.zip`。二者都必须登记到 `acceptance.json` 并经过成品审查。

