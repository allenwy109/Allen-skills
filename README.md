# Allen 的方法论 Skills

一套可在 Claude Code 和 Codex 中使用的 Agent Skills 分析系统：给它一家企业、一个创业点子或技术、一个话题、一份商业计划书或一个个人问题，它会拆问题、选对方法、联网核实关键事实、用独立的审查者挑毛病，最后经故事线整理。五个应用固定交付一份主交付物和一份支撑文件包（ZIP）。主交付物默认是 `out-report` 生成的 A4 正式阅读报告；用户明确要路演或演示稿时改为 `out-deck`；只有用户明确同时要求时才交付两种媒介。用户可以直接附 PDF、Word、PPT。

整体设计见 [ARCHITECTURE.md](ARCHITECTURE.md)。

## 安装

这套 skill 可以在 Claude Code、Codex、claude.ai 聊天、Agent SDK 里用，但能力不同（联网核实、独立子代理审查、正式报告）。**先看 [INSTALL.md](INSTALL.md) 的对比表，再选在哪里用。**

Claude Code 和 Codex 的安装方式：

```bash
git clone https://github.com/allenwy109/Allen-skills.git
cd Allen-skills
./install.sh --claude        # Claude Code：~/.claude/skills
./install.sh --codex         # Codex：~/.codex/skills
./install.sh --both          # 两边都装
./install.sh --codex --render-deps  # 额外准备正式报告、图表、海报的依赖
```

上传到 claude.ai 时，先运行 `python3 tools/build-zips.py` 打包，每个 skill 一个 zip（out-* 依赖本机引擎，不打包）。

## 怎么用

五个应用可以明确调用，命令后直接写要求并附文件：

| 应用 | Claude Code | Codex | 处理重点 |
|---|---|---|---|
| 验证创业点子 | `/allen-idea` | `/prompts:allen-idea` 或 `$allen-idea` | 多轮澄清、路径比较、需求与潜在竞品、短中长期前景 |
| 了解企业 | `/allen-company` | `/prompts:allen-company` 或 `$allen-company` | 企业全景、团队与人才价值 |
| 资本市场对接与表现 | `/allen-capital` | `/prompts:allen-capital` 或 `$allen-capital` | 融资阶段、资本匹配、我方参与方式 |
| 上下游机会 | `/allen-ecosystem` | `/prompts:allen-ecosystem` 或 `$allen-ecosystem` | 客户、供应商、渠道、技术与交付伙伴 |
| 评审 BP | `/allen-bp-review` | `/prompts:allen-bp-review` 或 `$allen-bp-review` | 证据、内容、故事线和逐页修改 |

也可以直接说要做什么，由 router 判断：

- “帮我分析一下 XX 公司，我们在考虑和它合作。”
- “我有一项低成本机器视觉技术，想比较几种创业方向并判断是快钱还是长期机会。”
- “研究一下 2026 年国内储能行业，值不值得进？”
- “评审这份 BP。”（附文件）
- “我总是拖延，怎么办？”

只想用一个方法时，直接点名：“用 SWOT 分析一下……”。默认（L2）就交正式报告；说“简单说说”是对话里快答（L1），说“深入分析”是 L3。正式报告要经过版式规划、验收和独立审查，比 Markdown 慢得多。

默认正式阅读报告由 `out-report` 交付 A4 HTML + PDF。用户明确要路演或演示稿、汇报、投屏、幻灯片或 deck 时，改用 `out-deck`。同一任务可以同时交付两种媒介，二者不互相替代。

## 目录

| 层 | Skill | 用途 |
|---|---|---|
| 应用 | [allen-idea](allen-idea/) | 澄清创业想法，比较企业化路径并判断前景 |
| 应用 | [allen-company](allen-company/) | 了解企业，含团队和人才价值 |
| 应用 | [allen-capital](allen-capital/) | 判断资本市场对接、融资表现与参与方式 |
| 应用 | [allen-ecosystem](allen-ecosystem/) | 分析上下游和产业协同机会 |
| 应用 | [allen-bp-review](allen-bp-review/) | 评审 BP 的证据、内容、故事线和页面表达 |
| 入口 | [router](router/) | 判断场景和投入深度，建任务文件夹；附各场景的系统提示词模板 |
| 场景 | [scene-idea](scene-idea/) | 给创业想法或技术：澄清、路径比较、需求与竞品研究、前景判断 |
| 场景 | [scene-company](scene-company/) | 给一家企业：诊断、合作、投资、内部管理 |
| 场景 | [scene-topic](scene-topic/) | 给一个话题或行业：研究并给出判断 |
| 场景 | [scene-bp-review](scene-bp-review/) | 给一份商业计划书：核实说法、找漏洞、出评审意见 |
| 场景 | [scene-personal](scene-personal/) | 个人问题：时间、拖延、习惯、学习、决策、职业 |
| 能力 | [core-framing](core-framing/) | 拆问题：主导问题、子问题、关键事实清单 |
| 能力 | [core-method-select](core-method-select/) | 选方法：画像、前提检查、预演产出、回退 |
| 接收 | [core-intake](core-intake/) | 用户附的 PDF、Word、PPT：逐页全文、页面图片、表格，登记进证据账 |
| 能力 | [core-evidence](core-evidence/) | 检索与核实：统一来源评价、时效表、统一证据账、核实关口 |
| 能力 | [core-research](core-research/) | 开放问题的深度研究：原文快照、数据血缘、可独立核验的研究包 |
| 能力 | [core-diligence](core-diligence/) | 公司研究与尽调：主体与控制链、上市研报、18 个模块、财务比率、报告内容契约 |
| 能力 | [core-synthesis](core-synthesis/) | 综合：冲突与依赖、路线图、事前验尸，完整正文加附录 |
| 能力 | [core-storyline](core-storyline/) | 故事线：信息卡片、主线、内容稿、拆页和整册图表版式规划 |
| 质量 | [core-review](core-review/) | 独立子代理审查：事实核查员、红队、方法审查员、决策者视角、成品审查员；统一输出标准 |
| 输出 | [out-report](out-report/) | 正式阅读报告（A4 HTML + PDF） |
| 输出 | [out-deck](out-deck/) | 路演或演示稿（HTML + PDF + 讲者备注），report-forge 引擎 |
| 输出 | [out-chart](out-chart/) | 可编辑咨询图表（PPTX + PNG + HTML），thinkcell-charts 引擎 |
| 输出 | [out-poster](out-poster/) | 一页海报（PNG + HTML），onepager 引擎 |
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

## 渲染引擎与运行时

三个渲染引擎来自 [ZeroxZhang/zerox-skills](https://github.com/ZeroxZhang/zerox-skills)，都是 Apache-2.0 许可（含 onepager，上游目录有 `LICENSE.txt`），按固定 commit 原样放在 [vendor/](vendor/)，版本和每个文件的哈希记在 `vendor/vendor.lock`，补丁在 `vendor/patches/`。引擎目录里没有 SKILL.md，只能经 out-* 调用。

研究、尽调、故事线三项能力（core-research、core-diligence、core-storyline）是参照上游的能力说明用自己的话和代码重写的，没有复制上游文字和代码。

`tools/` 是公共运行时：统一证据账（`tools/lib/ledger.py`，字段只在 `tools/lib/schema/` 里定义）、应用状态机（`tools/app_runtime.py`）、支撑包生成器（`tools/package_support.py`）、统一验收（`tools/acceptance.py`）、环境检查（`tools/doctor.py`）。安装后它和 vendor 一起放在对应平台的 skills 目录下：Claude Code 是 `~/.claude/skills/_allen-runtime`，Codex 是 `~/.codex/skills/_allen-runtime`。

## 维护

- `python3 tools/build-zips.py`：把每个 skill 打成 zip，用于上传 claude.ai。
- `python3 tools/validate.py`：检查 skill 结构、跨 skill 引用、卡片必备小节、选法表格式、vendor 完整性、schema。PR 上会自动跑。
- `tools/selftest.sh`：全部单元测试、各 skill 的脚本测试和三个引擎的测试；`tools/selftest.sh --e2e` 另跑端到端冒烟（文字要求 + 三份文件 → 正式报告、图表、海报 → 验收）。
- `python3 tools/doctor.py`：检查出成品所需的依赖。
- [tests/method-selection-cases.md](tests/method-selection-cases.md)：13 道选方法测试题，改选法表或卡片后重跑。
- 加新方法：在对应方法库加卡片（必备小节见 validate.py），在 method-index.md 登记，在 SKILL.md 选法表加一行。
