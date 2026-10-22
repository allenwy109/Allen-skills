# 转换映射表

我们的格式（证据账、slides.json、图表 spec）到三个引擎输入的映射，是转换脚本的唯一依据（设计 §6.3）。每个引擎一节，随对应的输出 skill 一起写定并配测试。目前已写定：thinkcell（out-chart）。报告引擎和海报引擎的映射，分别随 out-report 和 out-poster 写定。

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
