---
name: allen-bp-review
description: 评审企业 BP、融资路演稿或商业计划材料的应用入口。判断目标听众、叙事、产品竞争力、市场前景、竞品、商业模式、经营与团队说法是否完整可信，逐页指出问题并给出修改优先级、新故事线和待补证据。用户要求评审 BP、路演材料、融资材料写得好不好或如何增强时使用。
---

# 评审 BP

先完整读取 `references/system-prompt.md`。应用 ID 固定为 `allen-bp-review`，主场景固定为 `../scene-bp-review/`；不要重新交给 router 猜场景。

## 执行要求

L2、L3 用 `<运行时>/tools/app_runtime.py` 控制全流程。后台使用 `../core-intake/`、`../core-framing/`、`../core-diligence/`、`../core-evidence/`、`../core-research/`、`../core-method-select/`、`../core-review/`、`../core-synthesis/`、`../core-storyline/` 和 `../out-report/`。

评审不能只看文字和版式。产品竞争力、市场前景、竞品与替代方案、商业模式、经营进展和团队说法是强制基础模块；先核实关键主张，再判断表达是否成立。

## 强制输出

- 材料面向的读者和希望触发的行动；
- 一句话结论、主要优点和主要阻碍；
- BP 说法与核实结果的差异；
- 叙事主线和结构问题；
- 逐页或逐区块问题；
- 建议删除、合并、补充和重写的内容；
- 缺失页面、证据和材料；
- 修改优先级与建议新目录/故事线。

不得为了增强说服力而润色未经证明的数字和主张。证据不足时应建议补证据或降低表达强度。

## 交付

一份 BP 评审与修改建议主报告（PDF + HTML）和一份 `supporting-package.zip`。逐页问题和修改清单可进入主报告附录及支撑包。二者都必须登记到 `acceptance.json` 并经过成品审查。

