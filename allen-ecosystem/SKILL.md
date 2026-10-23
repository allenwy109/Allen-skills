---
name: allen-ecosystem
description: 分析一家企业与企业生态中的上下游机会。接收 BP、公司简介、产品资料、官网和用户说明，识别潜在客户、供应商、渠道、系统集成商、技术与交付伙伴，给出合作场景、价值交换、匹配条件、阻碍和内部企业库检索标准。用户提到销售机会、商机、客户对接、供应商、渠道、上下游或产业协同时使用。
---

# 上下游机会

先完整读取 `references/system-prompt.md`。应用 ID 固定为 `allen-ecosystem`，使用 `../scene-company/` 编排，尽调 purpose=`partnership`；不要重新交给 router 猜场景。

## 执行要求

L2、L3 用 `<运行时>/tools/app_runtime.py` 控制全流程。后台使用 `../core-intake/`、`../core-framing/`、`../core-diligence/`、`../core-evidence/`、`../core-research/`、`../core-method-select/`、`../core-review/`、`../core-synthesis/`、`../core-storyline/` 和 `../out-report/`。

先做企业、产品竞争力、市场、竞品、商业模式和交付能力的基础判断，再分析连接机会。不得把泛泛的行业相关性当成商机。

## 强制输出

- 企业的产业链位置；
- 下游客户、上游供应商、渠道与集成商、技术伙伴、交付伙伴；
- 每种关系解决的问题、价值交换、采购或合作触发条件；
- 合作所需能力、证明材料、主要阻碍和优先级；
- 用于内部企业储备库检索的结构化条件。

未接入内部企业库时，只输出企业类型和匹配标准，不虚构具体企业。接入后，具体候选名单默认只放内部支撑文件，不向项目方披露或承诺引荐。

## 交付

一份产业协同与上下游机会主报告（PDF + HTML）和一份 `supporting-package.zip`。二者都必须登记到 `acceptance.json` 并经过成品审查。

