# Allen 的方法论 Skills

一套用 Claude skill 搭起来的分析系统：给它一家企业、一个话题、一份商业计划书或一个个人问题，它会拆问题、选对方法、联网核实关键事实、用独立的审查者挑毛病，最后交付一页结论或正式报告。

整体设计见 [ARCHITECTURE.md](ARCHITECTURE.md)。

## 安装

这套 skill 可以在 Claude Code、Claude Code 网页版、claude.ai 聊天、Agent SDK 里用，但能力不同（联网核实、独立子代理审查、正式报告）。**先看 [INSTALL.md](INSTALL.md) 的对比表，再选在哪里用。**

最常用的方式是 Claude Code：

```bash
git clone https://github.com/allenwy109/Allen-skills.git
cd Allen-skills
./install.sh                 # 装到 ~/.claude/skills，含固定版本的 zerox skill
./install.sh --remove-old    # 从旧版升级时，删掉 consulting-analysis 等三个旧 skill
```

上传到 claude.ai 时，先运行 `python3 tools/build-zips.py` 打包，每个 skill 一个 zip。

## 怎么用

直接说要做什么即可，router 会判断场景：

- “帮我分析一下 XX 公司，我们在考虑和它合作。”
- “研究一下 2026 年国内储能行业，值不值得进？”
- “评审这份 BP。”（附文件）
- “我总是拖延，怎么办？”

只想用一个方法时，直接点名：“用 SWOT 分析一下……”。想要正式报告时加一句“出正式报告”或“深入分析”。

## 目录

| 层 | Skill | 用途 |
|---|---|---|
| 入口 | [router](router/) | 判断场景和投入深度，建任务文件夹；附各场景的系统提示词模板 |
| 场景 | [scene-company](scene-company/) | 给一家企业：诊断、合作、投资、内部管理 |
| 场景 | [scene-topic](scene-topic/) | 给一个话题或行业：研究并给出判断 |
| 场景 | [scene-bp-review](scene-bp-review/) | 给一份商业计划书：核实说法、找漏洞、出评审意见 |
| 场景 | [scene-personal](scene-personal/) | 个人问题：时间、拖延、习惯、学习、决策、职业 |
| 能力 | [core-framing](core-framing/) | 拆问题：主导问题、子问题、关键事实清单 |
| 能力 | [core-method-select](core-method-select/) | 选方法：画像、前提检查、预演产出、回退 |
| 能力 | [core-evidence](core-evidence/) | 检索与核实：来源分级、时效表、证据台账、核实关口 |
| 能力 | [core-synthesis](core-synthesis/) | 综合：冲突与依赖、路线图、事前验尸、一页结论 |
| 质量 | [core-review](core-review/) | 独立子代理审查：事实核查员、红队、方法审查员、决策者视角 |
| 方法库 | [lib-consulting](lib-consulting/) | 管理咨询方法，28 张卡片 |
| 方法库 | [lib-management](lib-management/) | 企业内部管理方法，24 张卡片 |
| 方法库 | [lib-personal](lib-personal/) | 个人效率方法，21 张卡片 |

方法库的结构：

```
lib-*/
├── SKILL.md                    选法表：情况 | 首选 | 前提 | 换用
└── references/
    ├── method-index.md         方法清单：适用、不适用、出处
    └── methods/                方法卡片：前提与不能推出什么、换用、步骤、模板、常见误用
```

## 第三方 skill

正式报告、深度研究和公司尽调用的是 [ZeroxZhang/zerox-skills](https://github.com/ZeroxZhang/zerox-skills)。`install.sh` 按 [zerox.lock](zerox.lock) 固定的版本从上游安装，**不把它的代码复制进本仓库**：其中 deep-research、due-diligence、storyline、onepager 上游没有许可文件，只能安装使用，不能再分发。想改用自己的 fork，设置 `ZEROX_REPO` 即可。

## 维护

- `python3 tools/build-zips.py`：把每个 skill 打成 zip，用于上传 claude.ai。
- `python3 tools/validate.py`：检查 skill 结构、跨 skill 引用、卡片必备小节、选法表格式。PR 上会自动跑。
- [tests/method-selection-cases.md](tests/method-selection-cases.md)：12 道选方法测试题，改选法表或卡片后重跑。
- 加新方法：在对应方法库加卡片（必备小节见 validate.py），在 method-index.md 登记，在 SKILL.md 选法表加一行。
