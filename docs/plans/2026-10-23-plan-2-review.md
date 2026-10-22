# 计划 2（统一证据账）审查记录

## 执行方式

用户要求本会话不使用子代理，所以计划 2 没有独立子代理演练和审查。用三种办法代替：

1. **先跑通再写计划**：全部代码先在仓库的临时副本里写好并跑通，然后才写成计划文档。
2. **变异检查**：故意把两条检查规则改坏，确认对应测试会失败（3 个失败），证明测试不是空跑。
3. **逐列核对**：用脚本把尽调 13 张表的每一列、深度研究快照头的 21 个字段，逐个对照到 schema 字段或写明的改名。两处未对上的都是脚本映射的误报；补写了一处改名说明（来源的 locator 拆为 url 和 original_files）。

以上都由执行者完成，**未经独立审查**。

## 完成标志（设计 §12 第 2 步）

| 标志 | 结果 |
|---|---|
| ledger、slides、sidecar 三个 schema 定稿 | 三个文件都已提交，自检干净（测试 `test_repository_schemas_are_clean`，validate 第 6 项也会检查） |
| ledger.py 单元测试通过 | 35 个测试通过（含变异检查，以及"规则常量都在 schema 里"的测试） |
| core-evidence 改读新证据账 | SKILL.md 第 1、6、8 节，source-tiers.md，证据账说明都已改写；文档里的 Python 示例照着在临时任务上实际跑通（check 0 错误）；validate 检查文档里的字段名和枚举值都在 schema 里 |
| 其他 | 单元测试共 94 个通过；validate 错误 0 个 |

## 设计 §8.2 自审

| 标准 | 结论 |
|---|---|
| 每个脚本有测试，且覆盖错误路径 | 满足：非法记录被拒且文件不变、ID 冲突、损坏的 JSONL、patch 改 id、合并时来源 ID 冲突、命令行退出码 1 和 2 都有测试 |
| 只用标准库 | 满足（fcntl 只在 macOS 和 Linux 上有，与本项目的运行环境一致） |
| 路径通过 runtime 解析 | 证据账位置由任务文件夹参数决定；schema 目录相对模块自身定位。本步不涉及引擎路径 |
| 枚举来自 schema | 满足：ledger.py 规则里写到的枚举值，由 `RuleConstantsTest` 保证都在 schema 里；validate 检查 core-evidence 文档里的枚举值 |
| 没有 TODO 和占位 | 满足 |

## 有意留到后续计划的事项

- 快照文件头与 sources 的一致性检查：计划 6。
- 渲染 02_info_cards.md：计划 5。
- `ledger export`（转换成引擎格式）：计划 4。
- core-evidence 第 7 节（交给 zerox-deep-research）改为 core-research：计划 6。
- 其他 skill 里 `03_evidence.md` 路径的改动：计划 8。
