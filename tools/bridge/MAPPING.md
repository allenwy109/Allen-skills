# 转换映射表

我们的格式（证据账、slides.json、图表 spec）到三个引擎输入的映射，是转换脚本的唯一依据（设计 §6.3）。每个引擎一节，随对应的输出 skill 一起写定并配测试。目前已写定：thinkcell（out-chart）、onepager（out-poster）。报告引擎的映射随 out-report 写定。

## 公共规则（所有引擎）

- 数字只来自证据账的指标：取值用 `tools/lib/metrics.py`。公式算法与报告引擎一致；显示按指标的 `decimals` 做十进制半入（中点远离零），不出现 -0。
- 指标能进成品的条件（`metrics.check_presentable`）：
  - 被至少一条主张引用；
  - 状态不是 `missing` 或 `not_applicable`；
  - 引用它的主张里至少有一条是 `verified`、`single_source`，或 `conflicting` 且冲突表已写采信理由。
- 来源说明由 `source_ids` 生成，格式是 `<来源标题>（<来源 ID>）`，多个来源用"；"连接。
- 估算、预测、假设、判断、建议类主张的数值进入成品时，必须注明身份。
- 状态为 `approximate` 的指标进入成品时，必须注明"近似"。

## thinkcell（`tools/bridge/to_thinkcell.py`，用于 out-chart）

| 我们的图表 spec | thinkcell spec | 规则 |
|---|---|---|
| `data` 里的 `{"metric": "m-…"}` | 同位置的数值 | 按上面的公共规则取值、半入。指标不能进成品就拦下 |
| `data` 里的裸数字 | — | 拦下：追溯不到证据账 |
| `data.axis_break`、`format`、`delta_format`、`scale_max`、`decimals`、`font_size` | 原样 | 版式和格式参数，允许写数字 |
| `decorations[].value`（value_line） | 数值 | 必须是指标引用 |
| `decorations[].from` / `to`、`highlight`、`callouts` 里的位置数字 | 原样 | 位置参数 |
| `source_ids` | `source` | 拼成来源说明；写了 `source` 就拦下 |
| `footnote` | `footnote` | 有近似值时追加"部分数值为近似值"；有非事实数值时追加"含……数值，不是实际数据" |
| 其余字段（`type`、`title`、`subtitle`、`unit`、`theme`、`palette`、`highlight`、`callouts`） | 原样 | `type`、`title`、`unit`、`data`、`source_ids` 必填 |

测试：`tools/tests/test_bridge_thinkcell.py`（正向 5 例；反向 10 例：裸数字、缺失指标、未核实主张、无人引用的指标、不存在的指标、不存在的来源、缺来源、手写来源、缺标题、装饰写裸数字）；端到端测试在 `out-chart/scripts/tests/test_out_chart.py`。

## onepager（`out-poster/scripts/out_poster.py`、`tools/bridge/poster_numbers.py`）

onepager 没有"输入 → HTML"的渲染器，海报 HTML 由作者手写，所以这里不是逐字段转换，而是"给作者的事实清单 + 成品回查"。

| 我们 | onepager | 规则 |
|---|---|---|
| 能进成品的主张（公共规则） | `source/<slug>-facts.json`（项目 source 目录） | 每条主张给出陈述、身份、核实状态、指标显示值和单位、来源说明 |
| 事实或数据类、已核实或单一来源主张的指标 | BigNumber 候选（`bignum_candidates`） | E1 只能用候选；不足 2 个改 E2 |
| 来源说明 | 页面上的来源文字；IR 和蓝图的 `source_refs` 写来源 ID | `project.py validate --require-sources` 检查 |
| 海报 HTML 上的数字 | — | 回查：必须等于某个能进成品的指标的显示值；年份（1900–2100 的 4 位整数）和编号除外；`--allow` 显式放行的要写进验收 |
| 非事实身份的指标 | 页面文字 | 数字前后 20 字内要有"估算、预测、假设、判断、建议、约、预计"之一 |
| `bignum-value` 元素里的数字 | BigNumber | 只能用已核实或单一来源主张的指标 |

测试：`tools/tests/test_poster_numbers.py`（5 例）；端到端测试在 `out-poster/scripts/tests/test_out_poster.py`（4 例）。
