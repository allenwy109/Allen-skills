---
name: out-chart
description: 出可编辑的咨询风格图表：把故事线里的图表 spec（数字全部是证据账里的指标引用）交给 think-cell 风格的图表引擎，输出可编辑 PPTX、PNG 预览和可改字的 HTML，并登记验收。55 种单图，加 dashboard、facet 拼版和 CAGR、差值等装饰；渲染前先校验数据够不够画这张图；中文完整显示。core-storyline 拆页后需要单独交付图表时调用；用户要"把这组数据画成瀑布图 / Mekko / 咨询图表"时也可以单独使用，但数字仍要先登记进证据账。正式报告里的图由 out-report 自己画，不用本 skill。
---

# 出图表

图表里的每个数字都要能追回证据账。所以图表 spec 里不写数字，只写指标引用，由脚本取值；数据不够画时先拦下，不硬画。

## 1. 写图表 spec

放在任务文件夹的 `07_storyline/charts/<名>.json`。格式和引擎的 spec 相同（字段见 `<运行时>/vendor/thinkcell-charts/docs/CATALOG.md`），只有三点不同：

1. `data` 里的每个数写成 `{"metric": "m-0001"}`。裸数字会被拦下。版式和格式参数（`axis_break`、`format` 等）可以写数字。`value_line` 装饰的 `value` 也要写指标引用。
2. 不写 `source`，写 `source_ids`（来源 ID 列表），脚本会拼成来源说明。
3. 引用的指标必须能进成品：被主张引用；不是缺失或不适用；所属主张为已核实、单一来源，或冲突已处理。估算、预测等数值会自动在图注里说明。

```json
{"id": "revenue", "type": "column", "title": "星河数据科技收入两年增长近八成", "unit": "万元", "source_ids": ["M001"],
 "data": {"categories": ["2024", "2025"], "series": [{"name": "收入", "values": [{"metric": "m-0001"}, {"metric": "m-0002"}]}]}}
```

- **标题写结论**，不写话题；单位必填。
- **选图**：core-storyline 拆页时可以调用引擎的推荐（`tc_advise.py`，给数据和想说明的结论，得到首选加 2 个备选）。推荐规则只看数据形态，不懂业务，采不采纳由故事线结合受众判断，不采纳时写理由。推荐草稿会把空值填成 0，转成我们的 spec 时一律改回缺失，并提示补数。
- **拼版和装饰**：多指标乘多分组用 `facet`，自由拼版用 `dashboard`（见引擎 `docs/DASHBOARD.md`）；装饰支持 `cagr`、`total_diff`、`diff`、`value_line`。

## 2. 出图

```bash
python3 <本 skill 目录>/scripts/out_chart.py <任务文件夹> <图表 spec...> --name <交付物名> [--theme 配色]
```

脚本依次做：

1. **转换**：取指标值（按指标位数十进制半入，和报告引擎一致），拼来源。有问题就停在这里，逐条列出。
2. **引擎校验**（`tc_validate`）：
   - "不能做"：拦下不渲染，按提示补数据或换图。只有用户明确接受折中时才加 `--force`，并在图注写明折中内容。
   - "能做但有问题"：照常渲染，记为警告。要么修改，要么在验收记录里写明处置。
3. **渲染**：可编辑 PPTX（全部是原生形状）、PNG（每张图一张）、可改字的 HTML，放在 `08_deliverables/charts/`。PNG 由 LibreOffice 转出；脚本会让它用上系统中文字体，否则中文会消失。
4. **登记验收**：条目 `chart-<名>`，写入转换、校验结果和数字追溯情况。

配色默认 `consulting_navy`，可选另外 7 套（`tc_render.py --list-themes`）。

退出码：0 已渲染；1 被转换或校验拦下；2 参数或环境错误。

## 3. 验收

渲染完成时状态是"不通过（尚未经过成品审查）"，还差两步：

1. **自检**（作者）：对照引擎 `docs/STYLE_SPEC.md` 的 §11 结论页四件套（结论式标题、基准、例外圈注、来源和截止日期）、§12 易误读护栏（达成率分母、百分点和百分比、红圈表示讨论重点、跨页日期对齐），看 PNG 有没有标签重叠、箭头压字、颜色含义错（正向用主色，负向用酒红或红）。可编辑 HTML 要实际打开试一次：改字、保存、重新打开后还能继续改。
2. **成品审查**：成品审查员看 PNG 和 PPTX 预览，按 `../core-review/references/output-standard.md` 写结论，用 `<运行时>/tools/acceptance.py <任务文件夹> review chart-<名> <结论.json>` 写入。

最后运行 `acceptance.py <任务文件夹> check`：只有"通过"才能说已完成；"有条件通过"要把条件告诉用户。
