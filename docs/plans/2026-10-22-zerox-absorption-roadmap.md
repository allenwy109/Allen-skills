# zerox 吸纳：实施路线图

依据：`docs/specs/2026-10-22-zerox-absorption-design.md`（v3.1，已获用户确认），下文"设计"均指该文档。

设计 §12 的 8 步，每步写成一份独立的实施计划。每份计划都要产出能单独测试的成果。一份计划在开始执行前才写，这样能用上前几步的实际产出（尤其是第 2 步定稿的 schema）。每份计划写完后，先由独立子代理审查，再执行。执行时每完成一个任务做一次审查，每完成一份计划做一次整体审查（设计 §8.2）。

| # | 计划文件 | 设计章节 | 依赖 | 完成标志（设计 §12） | 状态 |
|---|---|---|---|---|---|
| 1 | `2026-10-22-plan-1-runtime.md` | §6.1、§9 | 无 | doctor 全部通过；三个引擎自带测试通过；能力探测通过 | 已写 |
| 2 | `plan-2-ledger.md` | §3、§5.3 slides.json 扩展 | 1（runtime.py） | ledger、slides、sidecar 三个 schema 定稿；ledger.py 单元测试通过；core-evidence 改读新台账 | 待写 |
| 3 | `plan-3-intake.md` | §4 | 2 | 四份测试材料都能处理成标准结构，并登记进证据账 | 待写 |
| 4 | `plan-4-output.md` | §6、§8.3 | 1、2 | 用手写的 slides.json 和夹具证据账出三种成品；acceptance 只允许 storyline 相关检查为 skipped | 待写 |
| 5 | `plan-5-storyline.md` | §5.3 | 2、4 | 对照清单逐条完成；用真实流程重跑第 4 步的任务，acceptance 为 passed | 待写 |
| 6 | `plan-6-research.md` | §5.1 | 2 | 对照清单逐条完成；研究包能封包并通过 --final | 待写 |
| 7 | `plan-7-diligence.md` | §5.2 | 2、4、5 | 对照清单逐条完成；一个虚构公司的尽调任务走完报告链路，acceptance 为 passed | 待写 |
| 8 | `plan-8-wiring.md` | §2.1、§7、§11 端到端 | 1–7 | 端到端冒烟通过；validate.py、CI 通过；不再安装 zerox；安装到 `~/.claude/skills` | 待写 |

第 6 步只依赖第 2 步，可以和第 4、5 步并行。其余按顺序执行。

## 全部计划共用的约定

- 仓库：`~/Repos/Allen-skills`，分支 `design/zerox-absorption`。
- 提交作者：本机 git 没有配置用户信息，每次提交都用
  `git -c user.name="allenwy109" -c user.email="51287374+allenwy109@users.noreply.github.com" commit …`。
  提交信息末尾加一行 `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`。不修改用户的 git 配置。
- Python：我们自己写的脚本只用标准库（设计 §8.2）。测试用 `unittest`，统一运行命令为
  `python3 -m unittest discover -s tools/tests -t .`（在仓库根目录执行）。
- 不在第 8 步之前覆盖 `~/.claude/skills`。用户现在的旧版 skill 还在那里使用。验证一律装到临时目标目录。
- 不复制 deep-research、due-diligence、storyline 的任何文字或代码（设计 D3）；只依据 `docs/specs/inventory/` 下的能力清单。
