# 数据

数据表是数值记录的真源，放在 `03_evidence/data/`；证据账 metrics 通过 record_id 引用其中的记录。

## 1. 先定行粒度

开题时就写明每张表一行代表什么。数据需求定义先于大规模检索；每轮研究同时更新证据和数据，不能报告写完再反向凑表。

project 表的 data_status 三选一，并写 data_reason：

- available：允许有部分缺口，缺口写成记录或覆盖说明；
- unavailable：写明尝试过什么、限制是什么；
- not_applicable：写明为什么结构化记录对本任务没帮助，不建空目录。

检查脚本双向核对：声明不是 available 却有数据，或声明 available 却没有数据关联，都报错。

## 2. 文件

| 文件 | 内容 |
|---|---|
| `data/datasets.json` | 数组，每项 id、path（`data/extracted/…csv` 或 `data/curated/…csv`）、stage、grain（一行代表什么）、coverage（实际覆盖及与简报要求的差距）、limitations（没有写 none）。只登记实际非空的表 |
| `data/dictionary.csv` | 列 dataset_id、field、type（string、number、boolean）、description、unit（无单位写 n/a）、missing_rule；每张表的每一列一行，不多不少 |
| `data/README.md` | 使用说明、数据集与用途、范围与缺口、一条记录的追溯示例、使用限制 |
| `data/extracted/*.csv` | 提取层 |
| `data/curated/*.csv` | 整理层 |
| `analysis/` | 方法、选择或排除理由、复跑步骤和依赖；结果统一进 curated，不散放在 analysis |

## 3. 记录

公共字段：record_id、value、value_type、value_origin、status、source_id、source_locator、original_value、input_ids、method（模板另有 entity、metric、unit、period、geography、scope、missing_reason）。

- record_id 全局唯一且稳定，不因排序重编号（`M-R0001`、`A-R0001`）。
- value 里不混写单位；区间拆成上界、下界两条记录或两列。
- value_type：number、string、boolean。value_origin：reported（原始披露）、estimate（外部估计）、derived（本次计算或推断），它不等于置信度。
- status：present、missing、unavailable、not_applicable；不是 present 时 value 留空并写 missing_reason。**缺失不能填 0**。
- 数值记录必须写 entity、metric、unit、period、geography、scope；识别不了的写 unknown 并说明，但不能靠 unknown 绕过关键口径核验。
- 定性记录可以删掉数值专用列，加领域字段（对象、编码维度、事件日期等）。表内需要筛选时加 selection 和 selection_reason，并登记进字典。
- CSV 用 UTF-8、标准引号转义，空字符串表示缺失。

**提取层和整理层的约束互斥**：

| | 提取层 | 整理层 |
|---|---|---|
| 必须有 | source_id、source_locator、original_value（有值时） | input_ids（分号分隔）、method（指向 analysis/ 下的文件；原样选用也要写） |
| 不能有 | value_origin=derived、input_ids、method | source_id、source_locator |

## 4. 血缘

- 统一币种、单位、期间，或做计算，属于 derived；纯筛选或原样选用可以保留 reported、estimate，但同样要 input_ids 和 method。
- 不得自引用或循环依赖；没有值的输入推不出有值的结果。
- 情景假设写成明确标注的假设记录并附依据，不能把缺失偷偷补成事实。
- 方法里逐条说明输入的采用或排除理由；定性编码属于推断，整理层标 derived，方法里写编码标准和歧义。
- 更正：一条提取记录对应一次来源观察；更正只改 data 并写理由，快照不动，然后重算下游、重新检查。
- 独立导出数据时，连同 README、字典、全部传递依赖的输入、方法、来源索引和原件一起导出，不能只复制 curated（封包已经这样做）。

## 5. 子代理的数据交接

子代理写 `data/extracted/<代号>-*.csv`，并在 `03r_research/tasks/<代号>-data.json` 交接 `{"datasets": [...], "dictionary": [...]}` 草稿，由主线程合并进 datasets.json 和 dictionary.csv。没有数据就不生成空 CSV。

## 6. 机器能证明什么

检查脚本只能证明存在、路径、字段、关系、循环和类型；不能证明数字抄对、来源独立、口径可比、算式正确——这些由人工复核：从报告逐条回查关键数据，实际复跑计算或独立代入算式，并记录核对位置。
