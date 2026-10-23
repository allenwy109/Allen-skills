# 计划 8：接线、移除 zerox、文档与端到端冒烟 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 按设计 §2.1、§7、§11 把计划 1–7 的新能力接进 router 和四个场景：新的深度表、§3.1 的任务文件夹、core-intake 的先后顺序、core-research / core-diligence / core-storyline / out-* 的调用条件；取消"一页"和条数上限；移除 zerox（安装、校验、打包、CI、文档）；补端到端冒烟；最后安装到 `~/.claude/skills`。

**依据：** 设计 §2.1 改动清单、§3.1、§3.6、§4.1、§7.1、§7.2、§11。写法同计划 2–7。

## 开发中的发现与取舍

1. **防止绕过**：四个场景的交付一节都写明"正式报告、图表、海报只走 core-storyline 和 out-*，不直接调用 vendor 引擎，也不改用其他报告工具"；依赖不全时先交综合和故事线稿件并写明报告尚未生成，不拼一份冒充。validate.py 把对 `../zerox-*/` 的引用算作错误。
2. **深度只有一个真源**：router 第 2 节；场景只写本场景的差别，并注明真源。core-review 增加按深度开角色的表（L2 3 个、L3 5 个）。
3. **端到端冒烟抓到两个真问题**：
   - 报告引用了用户文件（intake 登记的 U 来源）时，参考资料页生成失败：引擎只接受 http/https 链接，而用户文件的地址是 `file:<文件名>`。改为只传网页链接，用户文件标"用户提供材料"。
   - 页内来源行把 `file:星河-年报摘要.pdf` 原样显示给读者；同一段代码对 original_files（对象列表）用字符串拼接，也是潜在错误。改为非网页来源只写类别（用户提供材料 / 本地存档材料）。
4. **实际看成品发现**：图表引擎把来源标签写死为英文"Source:"。按设计 D2"只打必要补丁"加 `vendor/patches/0001-thinkcell-chinese-source-label.patch`：来源文字含中文时用"来源："，否则不变（引擎自带的英文测试不受影响）。
5. 冒烟里的页面 HTML 由测试帮手按 pages.json 的绑定生成（补了 KPI 卡这种形式），版面是合成的，只证明链路和字段走得通；真实报告的版式由作者和成品审查员负责。
6. `--e2e` 单独运行（约 30 秒），不并进完整自检，完整自检仍跑单元、skill、结构和三个引擎的测试。
7. build-zips 只打包能在 claude.ai 上单独用的 skill：排除 out-* 和 `_allen-runtime`，也不再把 `__pycache__` 打进去；core-* 的脚本在 claude.ai 上跑不了，写进 INSTALL.md。

## 文件

| 文件 | 改动 |
|---|---|
| `router/SKILL.md`、`assets/brief-template.md`、`references/system-prompts.md` | 深度表、目录树、接收顺序；交付物选项；路径与交付措辞 |
| `scene-company`、`scene-topic`、`scene-bp-review`、`scene-personal` 的 SKILL.md | 接入新能力和输出层；路径；引用写法；取消"一页"和条数上限 |
| `core-synthesis/SKILL.md`、`core-review/SKILL.md` 与 `references/reviewer-prompts.md`、`lib-consulting/SKILL.md`、`lib-management/SKILL.md` | §7.1 措辞；审查角色表；提示词改读 `03_evidence/` 和最终报告 |
| `install.sh` | 不再装 zerox；`--remove-old` 只清理本脚本装过的 zerox-* |
| `tools/validate.py`、`tools/build-zips.py`、`.github/workflows/validate.yml`；删除 `zerox.lock` | 去掉 zerox 依赖；打包排除；CI 试装 |
| `tools/bridge/to_forge.py` | 参考资料与页内来源只用网页链接 |
| `vendor/patches/0001-…patch`、`vendor/vendor.lock` | 图表中文来源标签 |
| `tools/e2e/test_smoke.py`、`tools/selftest.sh --e2e` | 端到端冒烟 |
| `README.md`、`INSTALL.md`、`ARCHITECTURE.md` | 新结构、安装方式、审查角色数、onepager 许可更正 |
| 测试：`tools/tests/test_validate.py`、`test_install.py`、`test_build_zips.py`、`test_bridge_forge.py`；`out-chart/scripts/tests/test_out_chart.py`；`core-diligence/scripts/tests/gen_pages.cjs` | 对应上面的改动 |

## 任务与预期结果

- [ ] **Task 1 工具与测试**：`python3 -m unittest tools.tests.test_validate tools.tests.test_install tools.tests.test_build_zips tools.tests.test_bridge_forge` 先失败后通过；out-chart 5 个通过（需重新 sync vendor 并装 npm 依赖）。
- [ ] **Task 2 接线与文档**：`grep` 不再有 `zerox-`（引擎出处说明除外）、"一页结论"、`03_evidence.md`、`07_deliverables`；`python3 tools/validate.py` 0 个错误。
- [ ] **Task 3 端到端冒烟**：`tools/selftest.sh --e2e` → 5 个通过。
- [ ] **Task 4 收尾**：`tools/selftest.sh` 全部通过；审查记录；路线图。
- [ ] **Task 5 安装**：备份 `~/.claude/skills` → `./install.sh --remove-old`（不带 `--render-deps` 时运行时不含 npm 依赖，再运行 `--render-deps`）→ doctor 全部通过。
