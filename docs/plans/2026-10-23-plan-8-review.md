# 计划 8（接线、移除 zerox、文档、端到端冒烟）审查记录

用户要求本会话不使用子代理，以下验证由执行者完成，**未经独立审查**。

## 验证方式

- **对照设计逐条**：§2.1 改动清单里属于本步的每一行（router、四个场景、core-synthesis、core-review、两个方法库、install.sh、validate.py、build-zips.py、CI、三份文档、删除 zerox.lock）都已改；§7.1 的措辞表逐行处理；§7.2 深度表写进 router 第 2 节；§3.1 目录树写进 router 第 3 节；§4.1 接收顺序写进 router 第 0 节。
- **残留检查**：skill 文档和工具里不再有 `../zerox-*/` 引用、"一页结论"、`03_evidence.md`、`07_deliverables`（"一页海报""一页纸"等方法术语保留；引擎出处说明保留 zerox-skills 的名字）。validate.py 现在会把 zerox 引用算错误。
- **先测试后实现**：validate、install、build-zips、转换脚本、图表的 7 个新测试在旧实现上全部失败，落地后通过。
- **端到端冒烟**：文字要求 + 三份虚构用户文件（PDF、Word、PPT）→ core-intake → 临时文件夹改名为正式任务 → 证据账（用户文件的原文作为第二份证据支持收入主张）→ 分析与综合 → 故事线包 → 正式报告、图表、海报 → 三项交付物在成品审查前为"不通过"、审查后全部"通过"；改动报告 HTML 后验收失效。还验证了文件里像指令的句子只出现在接收产物里，不进任务单、不进报告。
- **实际看成品**：报告 5 页、图表 PNG、海报 PNG 逐张看过。

## 开发中发现并解决的问题

| 问题 | 怎么发现 | 处理 |
|---|---|---|
| 报告引用用户文件时，引擎生成参考资料页失败（只接受 http/https 链接） | 端到端冒烟 | 只传网页链接，用户文件标"用户提供材料"；补测试 |
| 页内来源行把 `file:星河-年报摘要.pdf` 原样显示；同一段代码把对象列表当字符串拼接 | 看成品第 2 页 | 非网页来源只写类别；补测试 |
| 图表来源标签写死为英文"Source:" | 看图表 PNG | vendor 补丁 0001：来源含中文时用"来源："；out-chart 测试用 OCR 核对 |
| 测试帮手不认 KPI 卡展品 | 端到端冒烟 | 帮手补上该形式 |
| 场景之间互相指向（BP 评审的交付"见 scene-company"） | 对照 ARCHITECTURE 的边界 | 各场景自写交付一节 |

## 尚存限制

- 冒烟里的页面 HTML、规划观察、审查稿是合成的，只证明链路和字段走得通；冒烟报告第 3 页大块空白来自合成帮手，真实报告的版式质量取决于作者和成品审查员。
- `--render-deps` 只支持 macOS（Homebrew）；云端和 Linux 的依赖安装没有实现，也没有实际跑过（INSTALL.md 已写明）。
- claude.ai 上传的 zip 里 core-* 的脚本依赖运行时，跑不了，只能按文档手工走流程。
- scene 文档的接线只能靠阅读核对，没有自动测试能证明模型实际会按这些说明调用；需要用真实任务试跑（ARCHITECTURE"后续计划"）。

## 完成情况

- 完整自检通过：单元 145、core-diligence 44、core-intake 16、core-research 39、core-storyline 32、out-chart 5、out-poster 4、out-report 5；validate 0 个错误（20 个 skill）；三个引擎自带测试全部通过（含打补丁后的 thinkcell 70 项）。
- 端到端冒烟 `tools/selftest.sh --e2e`：5 个通过。
- 安装到 `~/.claude/skills`：见下一节。

## 安装

- 安装前把 `~/.claude/skills` 整个备份到 `~/.claude/skills-backup-20261023`（含三个旧 skill 和 content-design）。
- `./install.sh --remove-old`：装入 20 个 skill 和 `_allen-runtime`；删除已被 lib-* 取代的 consulting-analysis、management-toolkit、personal-effectiveness；content-design 不是本脚本装的，保留未动；原本没有 zerox-*。
- `./install.sh --render-deps`：装 npm 依赖与字体、生成能力探测任务；看图验证后 `record_probe.py` 通过。
- 安装后的运行时 `doctor.py` 13 项全部通过；新 skill 已出现在 Claude Code 的可用 skill 列表里。
