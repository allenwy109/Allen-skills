# 安装与使用

这套 skill 可以在 Claude Code、Codex 和几个托管入口中使用。它们装法不同，能力也不同：联网核实、独立子代理审查、正式报告这三项，不是每个地方都有。

## 先选在哪里用

| 在哪里用 | 怎么装 | 联网核实 | 独立子代理审查 | 正式报告（HTML/PDF）、图表、海报 | 适合 |
|---|---|---|---|---|---|
| **Claude Code**（终端、桌面 App、VS Code / JetBrains 插件） | `./install.sh` 装到 `~/.claude/skills` | 有 | 有 | 可以（先运行 `install.sh --render-deps`） | **主力推荐**：L2、L3 全流程 |
| **Codex**（CLI、App、IDE 或云端环境） | `./install.sh --codex` 装到 `$CODEX_HOME/skills`，默认 `~/.codex/skills` | 取决于环境网络策略 | 取决于宿主是否提供子代理 | 可以（先运行 `--render-deps`） | L1～L3；适合在代码工作区内运行 |
| **Claude Code 网页版**（claude.ai/code，云端运行） | 云端环境的 setup script 里运行 `install.sh` | 取决于环境的网络设置 | 有 | `--render-deps` 目前只支持 macOS（Homebrew），云端 Linux 需另行准备依赖，未实际跑过 | 不开电脑也能跑、按项目管理 |
| **claude.ai 聊天**（网页、桌面、手机 App） | 每个 skill 打成 zip，在设置里逐个上传 | 有网页搜索；skill 内脚本的联网受设置限制 | **没有**，自动降级为自审 | 不能（out-* 不打包；core-* 的脚本也跑不了） | L1 快答、个人问题、快速看 BP |
| **Agent SDK**（以后封装成自己的应用） | `install.sh --target <项目>/.claude/skills` | 有（放行搜索工具） | 有 | 可以 | 把某个场景做成固定入口或产品 |
| **Claude API**（Messages API + Skills API） | 通过 `/v1/skills` 上传 | skill 运行环境**不能联网** | 需自己实现 | 不能 | 不推荐 |

说明：

- skill 在各处之间**不会同步**，在哪里用就要在哪里装。
- 同时使用 Claude Code 和 Codex 时可运行 `./install.sh --both`；两边各有一份技能与运行时。
- “独立子代理审查”是 core-review 的核心。没有子代理的地方，它会按清单自审，并在报告里写明“未经独立审查”。
- 跨 skill 引用（例如 scene-company 调用 `../core-evidence/`）依赖所有 skill 装在同一个目录。Claude Code 和 Agent SDK 都满足；claude.ai 上传后能否按这种方式互相引用，**还没有验证**。

---

## 1. Claude Code（推荐）

适用于终端里的 `claude`、Claude 桌面 App 里的 Claude Code、IDE 插件。

```bash
git clone https://github.com/allenwy109/Allen-skills.git
cd Allen-skills
./install.sh
```

默认把本仓库的 24 个 skill 和运行时 `_allen-runtime`（vendor 引擎 + tools）复制到 `~/.claude/skills/`，并把四个 `/allen-*` 入口装到 `~/.claude/commands/`。常用参数：

| 参数 | 作用 |
|---|---|
| `--link` | 用软链接代替复制，在仓库里改 skill 立即生效（自己维护时用） |
| `--render-deps` | 安装出成品所需的依赖：Homebrew 装 Poppler、Tesseract（含中文）、Pandoc、LibreOffice；Python 虚拟环境（默认 `~/.cache/allen-skills/venv`，可用 `ALLEN_VENV` 改）；Playwright Chromium；报告引擎的 npm 依赖与字体；最后生成能力探测任务。需要 Node.js 20+、Python 3.10+、Google Chrome |
| `--target DIR` | 装到别的目录，例如某个项目的 `.claude/skills` |
| `--force` | 覆盖目标目录里不是本脚本装的同名 skill |

更新：`git pull && ./install.sh`。复制模式重新安装会清掉运行时里的 npm 依赖和探测结果，要出成品时再运行一次 `--render-deps`。

`--render-deps` 结束时会提示一步看图验证：在 Claude Code 里让 Claude 打开探测图片、写下看到的内容，再运行 `record_probe.py`。之后运行 `python3 ~/.claude/skills/_allen-runtime/tools/doctor.py`，全部"通过"才能出正式报告。

装好后打开 Claude Code，直接说要做什么即可（见文末“怎么用”）。

## 2. Codex

适用于 Codex CLI、桌面 App、IDE 集成和带可写用户目录的 Codex 云端环境：

```bash
git clone https://github.com/allenwy109/Allen-skills.git
cd Allen-skills
./install.sh --codex
```

默认安装到 `${CODEX_HOME:-$HOME/.codex}/skills`，四个自定义 prompt 安装到 `${CODEX_HOME:-$HOME/.codex}/prompts`。可用 `/prompts:allen-company` 等命令，或直接用 `$allen-company` 等 Skill 名称。安装后重新启动 Codex 会话，让它重新扫描。开发本仓库时可加 `--link`，仓库中的改动会立即反映到安装目录：

```bash
./install.sh --codex --link
```

Codex 宿主提供子代理时，`core-review` 会用 `spawn_agent` 并行启动独立审查者；没有子代理能力时，按原有规则降级为自审并标注“未经独立审查”。联网研究同样服从当前 Codex 环境的网络策略。

要生成 HTML/PDF、图表和海报，再运行：

```bash
./install.sh --codex --render-deps
python3 "${CODEX_HOME:-$HOME/.codex}/skills/_allen-runtime/tools/doctor.py"
```

macOS 会通过 Homebrew 安装系统工具。Linux 会检查 Poppler、Tesseract 中文包、Pandoc、LibreOffice 和中文字体；缺少时按脚本给出的发行版命令安装，再重跑。Chrome 与 LibreOffice 支持 PATH 自动发现，也可用 `ALLEN_CHROME`、`ALLEN_SOFFICE` 显式指定。

## 3. Claude Code 网页版（云端）

云端每次开新会话都是一台新机器，装好的东西不会保留，所以要在**云端环境的 setup script** 里每次自动安装：

1. 在 claude.ai/code 的环境设置里新建一个云端环境（Add cloud environment）。
2. Setup script 填：

   ```bash
   git clone --depth 1 https://github.com/allenwy109/Allen-skills.git /tmp/Allen-skills
   /tmp/Allen-skills/install.sh
   ```

   正式报告需要的依赖可用 `--render-deps` 准备。Linux 云端需先安装 Poppler、Tesseract 中文包、Pandoc、LibreOffice 和中文字体；脚本会检查这些系统工具，再安装 Python、Playwright 和 Node 依赖，最后用 `doctor.py` 检查。
3. 网络设置要允许访问 GitHub（下载本仓库）；做联网核实还要允许访问一般网站。

具体可用性取决于云端环境是否允许安装系统包和下载浏览器。

## 4. claude.ai 聊天（网页、桌面、手机 App）

需要 Pro、Max、Team 或 Enterprise 套餐，并在设置里打开代码执行。上传的 skill 只对自己可见。

1. 打包：

   ```bash
   python3 tools/build-zips.py      # 在 dist/ 下每个 skill 一个 zip（out-* 不打包）
   ```

2. 在 claude.ai 的设置（Settings → Features / Capabilities 的 Skills 部分）里逐个上传 zip。至少上传：`router`、`core-intake`、`core-framing`、`core-method-select`、`core-evidence`、`core-synthesis`、`core-review`、三个 `lib-*`，以及要用的 `scene-*`。

限制：

- 没有子代理，core-review 会降级为自审。
- 正式报告、图表、海报依赖本机的渲染引擎，这里出不了；core-* 的脚本依赖运行时，也不能运行，只能按文档手工走流程。适合 L1 快答，交付 Markdown。
- 跨 skill 引用能否生效还没有验证，建议先用一个简单问题试一下：看它是否按 core-method-select 的步骤输出方法计划。

## 5. Agent SDK（自建应用）

SDK 从文件系统加载 skill，没有上传接口。

```bash
./install.sh --target /path/to/your-app/.claude/skills
```

```python
from claude_agent_sdk import query, ClaudeAgentOptions

options = ClaudeAgentOptions(
    cwd="/path/to/your-app",
    setting_sources=["user", "project"],   # 必须包含 project，才会加载 .claude/skills
    skills="all",
    allowed_tools=["Read", "Write", "Bash", "WebSearch", "WebFetch"],
    system_prompt="……",                     # 用 router/references/system-prompts.md 里对应场景的模板
)
```

要做成只做某一个场景的应用（例如只做 BP 评审），把 `skills` 改成需要的名单，并用对应的系统提示词模板。

## 6. Claude API

可以通过 Skills API（`/v1/skills`）上传，但 skill 的运行环境不能联网、不能安装包，核实和正式报告都做不了。除非另有需要，不建议用这种方式。

---

## 怎么用

四个固定应用的入口：

| 应用 | Claude Code | Codex |
|---|---|---|
| 了解企业 | `/allen-company <要求>` | `/prompts:allen-company <要求>` 或 `$allen-company` |
| 资本市场对接与表现 | `/allen-capital <要求>` | `/prompts:allen-capital <要求>` 或 `$allen-capital` |
| 上下游机会 | `/allen-ecosystem <要求>` | `/prompts:allen-ecosystem <要求>` 或 `$allen-ecosystem` |
| 评审 BP | `/allen-bp-review <要求>` | `/prompts:allen-bp-review <要求>` 或 `$allen-bp-review` |

命令后可以直接写用户提示词，并在同一条消息附文件。没有明确点名应用时，router 会判断场景和深度：

| 想做的事 | 可以这样说 |
|---|---|
| 分析一家企业 | “帮我分析一下 XX 公司，我们在考虑和它合作。” |
| 研究一个话题 | “研究一下 2026 年国内储能行业，值不值得进？” |
| 评审 BP | “评审这份 BP。”（附文件） |
| 个人问题 | “我总是拖延，怎么办？” |
| 只用一个方法 | “用 SWOT 分析一下……”“这个问题该用什么框架？” |
| 只核实 | “帮我核实一下这篇文章里的数据。” |

深度：默认 L2（完整流程、3 个审查者：事实核查员、红队、成品审查员；交正式报告）。说“简单说说”是 L1（对话里直接回答）；说“深入分析”是 L3（5 个审查者，研究和尽调做得更深，研究包封包）。深度的唯一标准在 router 第 2 节。

L2、L3 会在当前目录下建 `work/<日期>-<主题>/` 文件夹，里面是每一步的交接文件。四个应用交付 `report/` 中的主报告和 `supporting-package.zip`；两者是否完成都以 `08_deliverables/acceptance.json` 为准。

## 检查安装是否成功

- Claude Code：问一句“列出你能用的 skill”，应该能看到 `router`、`core-*`、`lib-*`、`scene-*`、`out-*`。
- Codex：重启会话后询问“列出 Allen skills”，应该能看到同一组 skill。
- 出成品的依赖：Claude Code 运行 `python3 ~/.claude/skills/_allen-runtime/tools/doctor.py`；Codex 运行 `python3 "${CODEX_HOME:-$HOME/.codex}/skills/_allen-runtime/tools/doctor.py"`。
- 维护者：`python3 tools/validate.py` 检查仓库结构；`tools/selftest.sh` 跑全部测试。

参考：[Agent Skills 概览](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/)、[Agent SDK 中的 skills](https://code.claude.com/docs/en/agent-sdk/skills)。
