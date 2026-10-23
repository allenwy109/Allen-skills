---
name: out-poster
description: 出一页海报（OnePage 信息图）：把已经核实的结论做成一张可以直接分享的图片（PNG，另附 HTML），横版、竖版、方形、长图四种尺寸，九种设计风格，可带 BigNumber 大数字。用的是 onepager 引擎的设计规范和检查脚本，海报 HTML 由作者照模板手写，所以出图后要把页面上的每个数字和证据账对一遍。正式报告做完、需要一张对外传播或手机分享的总结图时调用；用户要"做一张一页图 / 信息图 / 海报"时也可以单独使用，但用到的数字仍要先登记进证据账。
---

# 出一页海报

海报传播得最广，看的人最不会去核对。所以规则只有一条：**页面上的每个数字都能追回证据账**；做不到的数字不上海报。

## 1. 准备

```bash
python3 <本 skill 目录>/scripts/out_poster.py prepare <任务文件夹> --slug <英文短名> --title <标题> [--claims cl-0001,cl-0003]
```

- 在 `07_storyline/poster-work/<slug>/` 建 onepager 项目。
- 生成"可用事实清单" `source/<slug>-facts.json`：只收录能进成品的主张（已核实、单一来源，或冲突已处理）；数字已按显示规则算好；附带来源说明。
  - `bignum_candidates`：可以用作 BigNumber 的指标，只限事实或数据类、已核实或单一来源。
- 作者只用清单里的主张和数字，不另起数字。

## 2. 配置（不逐项问用户）

按场景给推荐配置，在回复里说明所用配置；用户可以只改其中一项（例如"改成 B6"）。

| 场景 | 默认配置 |
|---|---|
| 企业诊断、尽调结论 | A2 横版、B7 数据新闻、C2 中密度、T3 信息图、E1 |
| 行业研究、政策解读 | A1 长图、B7 数据新闻、C3 高密度、T3 信息图、E1 |
| 方案或产品介绍 | A4 竖版海报、B2 瑞士精密、C2 中密度、T1 商业说服、E1 |

- 署名（F）由调用方指定，或写"无"。
- BigNumber（E1）只用 `bignum_candidates`；不足 2 个时改用 E2（不带大数字）。这一条有意比核实关口更严：醒目的大数字不用有争议的值。
- 九种风格、四种尺寸、三种密度、四种类型的含义见 `<运行时>/vendor/onepager/UPSTREAM-SKILL.md` 第 2 阶段。

## 3. 写海报

照 `<运行时>/vendor/onepager/UPSTREAM-SKILL.md` 的第 3、4 阶段（内容重构、IR、设计意图、生成 HTML）和它引用的规范（design-styles、typography、layout-specs、visual-standards、cross-reference，模板 `assets/templates/base-skeleton.html`）做：

1. 内容蓝图 `blueprint.json`，写进项目目录。
2. IR `onepager.ir.json`：记录最终配置、模块、来源、设计意图。T4 海报必须写设计意图声明；技术类内容执行语言门控（解读必须是中文）。
3. HTML：单文件，CSS、SVG、图标内联；不用 Emoji、蓝紫渐变、无意义的发光和毛玻璃；固定高度的画布要显式分配行高。BigNumber 的大数字用 `bignum-value`，标签用 `bignum-label`（和模板一致，数字回查靠它识别）。
4. 文件名：`{主题}-{尺寸}-{风格}-{YYYYMMDD}[-vN].html`；迭代时追加版本号。
5. 页面要写来源；估算、预测等非事实数字，前后要注明身份（"预测""估算""约"等）。

## 4. 完成

```bash
python3 <本 skill 目录>/scripts/out_poster.py finish <任务文件夹> --slug <英文短名> --html <海报.html> \
  --A A2 --B B7 --C C2 --T T3 --E E1 --F <署名> [--allow 3]
```

依次做：

1. 静态检查（`quality_check`）和渲染检查（`render_check`）。**onepager 只接受两项都是 PASS 的构建**，警告也要修掉。
2. 数字回查（`tools/bridge/poster_numbers.py`）：页面上的每个数字都要等于某个能进成品的指标的显示值。
   - 4 位年份不算数据；来源编号（M001）、主张编号不算数字。
   - 确实不是数据的数字（如"3 个阶段"）用 `--allow` 放行，放行记录会写进验收。
3. 截图（尺寸按 A1–A4，默认 2 倍分辨率）、登记构建（`project.py record-build`）、项目校验（`validate --require-sources`）。
4. HTML 和 PNG 复制到 `08_deliverables/poster/`，登记验收条目 `poster-<slug>`。

退出码：0 已出海报；1 被检查拦下（没有出图）；2 参数或环境错误。

## 5. 验收

出图时状态是"不通过（尚未经过成品审查）"。成品审查员看 PNG，按 `../core-review/references/output-standard.md` 写结论，用 `<运行时>/tools/acceptance.py <任务文件夹> review poster-<slug> <结论.json>` 写入。

引擎检查管不到的问题，要靠看图发现，重点看：大块无用空白、文字溢出或遮挡、中文缺字、强调色是否过多、BigNumber 是否是页面上最大的文字、来源和署名在不在。
