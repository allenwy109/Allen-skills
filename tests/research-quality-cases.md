# 决策研究压力案例

用于前向测试技能是否会做出正确判断，而不只是生成结构完整的文件。

## Case 1：只有供应商案例的创业点子

- Depth: L2
- Input: 创业者用三篇供应商案例证明客户痛点普遍且愿意付费。
- Required outcomes:
  - decision-research.json 把供应商 source ID 列入 issuer_source_ids，并把发生率、付费意愿标为高风险。
  - 没有独立购买信号时，结论降级并记录反证与 validation_gap。
- Forbidden outcomes:
  - 不得把供应商案例数量当成市场普遍性或已验证付费意愿。

## Case 2：只列直接竞品的公司分析

- Depth: L2
- Input: 公司分析列出三家直接竞争者，却没有检查客户自建、人工替代和不购买。
- Required outcomes:
  - research_quality.py 返回 QUALITY_COMPETITION_LAYER。
  - 补齐 direct、indirect、diy、adjacent、do_nothing，或为不适用层提供 claim ref 后才可综合。
- Forbidden outcomes:
  - 不得仅凭三家直接竞品通过竞争门禁。

## Case 3：用大 TAM 证明需求的 BP

- Depth: L2
- Input: BP 用大型咨询机构的 TAM 预测声称市场需求已验证。
- Required outcomes:
  - TAM claim 只标为市场估算或预测，不能作为 purchase_signal。
  - 缺少真实购买信号时 research_quality.py 返回 QUALITY_PAIN_PURCHASE_SIGNAL。
- Forbidden outcomes:
  - 不得从 TAM 推出具体细分客户的痛点强度、发生率或购买意愿。

## Case 4：把监管指南写成法律义务

- Depth: L3
- Input: 研究把由被评机构发布的行业指导文件描述为企业必须履行的法律义务。
- Required outcomes:
  - claim_risk_assessments 使用 regulatory_obligation，并把发布方 source ID 列入 issuer_source_ids。
  - 只有发布方指南支持时返回 QUALITY_ISSUER_ONLY，除非缩窄主张且置信度为 low。
- Forbidden outcomes:
  - 不得把指南、征求意见稿或倡议直接写成法律义务。

## Case 5：比例适当的 L1 快答

- Depth: L1
- Input: 用户只要一个低风险、可逆的初步判断。
- Required outcomes:
  - 回答明确关键假设和未核实边界。
  - 保持 L1 快答，不运行 research_quality.py。
- Forbidden outcomes:
  - 不得创建 decision-research.json 或为了合同完整度扩成 L2 研究。
