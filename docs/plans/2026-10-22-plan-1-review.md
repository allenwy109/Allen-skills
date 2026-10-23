# 计划 1（渲染运行环境）审查记录

## 执行前审查（独立子代理，两轮演练）

- 第一轮：在临时副本里照计划执行 Task 1–9。发现 1 个阻塞问题（macOS bash 3.2 下"变量后面紧跟全角字符"会报 unbound variable 并退出）、5 个重要问题、7 个轻微问题，全部改进计划（提交 c4c73f1）。
- 第二轮：13 条意见全部确认改对；另有 5 条轻微问题，其中 4 条改进计划（提交 2fbde76），1 条审查员认为不必改。

## 执行中发现的问题

| 问题 | 原因 | 处理 |
|---|---|---|
| 完整自检在 thinkcell 浏览器测试失败（`.venv/bin/python ENOENT`） | 计划漏写了 `TC_PYTHON`：该测试默认去引擎目录下找 `.venv/bin/python` 来生成测试图表 | selftest 设置 `TC_PYTHON` 指向我们的虚拟环境；计划和设计 §9、§11 同步更新（提交 dcece0f）。没有修改引擎代码 |

## 完成标志（设计 §12 第 1 步）

| 标志 | 结果 |
|---|---|
| doctor 全部通过 | 13 项全部"通过"，exit=0 |
| 三个引擎自带测试通过 | report-forge：npm test、test:render、test:upgrade-render 全部通过。thinkcell：回归 70 项通过、0 失败；unittest 15 个通过；浏览器测试通过。onepager：30 个测试通过，没有跳过 |
| 能力探测通过 | 实际看图后作答，引擎返回 codeMatches=true、shapesMatch=true |
| 其他 | 单元测试 45 个通过；validate 错误 0 个；vendor 检查通过；仓库没有残留的未跟踪文件 |

## 整体审查（设计 §8.2）

用户要求这个会话不使用子代理，所以整体审查由执行者按清单自审，**未经独立审查**。

| 标准 | 结论 |
|---|---|
| 每个脚本有测试，且覆盖错误路径 | 满足：vendor_sync、runtime、install、doctor、record_probe、validate 都有测试，失败分支都有用例（doctor 有 16 个失败子用例）。selftest.sh 是 shell 编排脚本，由完整自检的实际运行验证 |
| 只用标准库、vendor 已有的依赖，或登记过的依赖 | 满足：我们写的 Python 只导入标准库；shell 用到的 rsync、patch 是系统自带 |
| 路径通过 runtime.py 解析 | 满足：doctor、record_probe、selftest 都从 runtime 取路径。install.sh 里的虚拟环境默认路径单独写了一份，已注明要与 runtime.venv_python 保持一致 |
| 枚举来自 schema | 本步不涉及 |
| 没有 TODO 和占位 | 满足 |

## 留到后续计划的事项

- 停止安装 zerox、删除 zerox.lock、`--remove-old` 清理 zerox-*、build-zips.py 排除 out-* 和 `_allen-runtime`：计划 8。
- 本次实测装在 `~/.cache/allen-skills/stage-skills`（软链接模式），`~/.claude/skills` 没有改动。
