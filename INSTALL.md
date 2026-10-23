# 安装与使用

这套 skill 可以在五种地方用。它们装法不同，能力也不同：联网核实、独立子代理审查、正式报告这三项，不是每个地方都有。

## 先选在哪里用

| 在哪里用 | 怎么装 | 联网核实 | 独立子代理审查 | 正式报告（HTML/PDF）、图表、海报 | 适合 |
|---|---|---|---|---|---|
| **Claude Code**（终端、桌面 App、VS Code / JetBrains 插件） | `./install.sh` 装到 `~/.claude/skills` | 有 | 有 | 可以（先运行 `install.sh --render-deps`；macOS 需 Homebrew） | **主力推荐**：L2、L3 全流程 |
| **Claude Code 网页版**（claude.ai/code，云端运行） | 云端环境的 setup script 里运行 `install.sh` | 取决于环境的网络设置 | 有 | `--render-deps` 目前只支持 macOS（Homebrew），云端 Linux 需另行准备依赖，未实际跑过 | 不开电脑也能跑、按项目管理 |
| **claude.ai 聊天**（网页、桌面、手机 App） | 每个 skill 打成 zip，在设置里逐个上传 | 有网页搜索；skill 内脚本的联网受设置限制 | **没有**，自动降级为自审 | 不能（out-* 不打包；core-* 的脚本也跑不了） | L1 快答、个人问题、快速看 BP |
| **Agent SDK**（以后封装成自己的应用） | `install.sh --target <项目>/.claude/skills` | 有（放行搜索工具） | 有 | 可以 | 把某个场景做成固定入口或产品 |
| **Claude API**（Messages API + Skills API） | 通过 `/v1/skills` 上传 | skill 运行环境**不能联网** | 需自己实现 | 不能 | 不推荐 |

说明：

- skill 在各处之间**不会同步**，在哪里用就要在哪里装。
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

默认把本仓库的 20 个 skill 和运行时 `_allen-runtime`（vendor 引擎 + tools）复制到 `~/.claude/skills/`，对所有项目生效。常用参数：

| 参数 | 作用 |
|---|---|
| `--link` | 用软链接代替复制，在仓库里改 skill 立即生效（自己维护时用） |
| `--render-deps` | 安装出成品所需的依赖：Homebrew 装 Poppler、Tesseract（含中文）、Pandoc、LibreOffice；Python 虚拟环境（默认 `~/.cache/allen-skills/venv`，可用 `ALLEN_VENV` 改）；Playwright Chromium；报告引擎的 npm 依赖与字体；最后生成能力探测任务。需要 Node.js 20+、Python 3.10+、Google Chrome |
| `--target DIR` | 装到别的目录，例如某个项目的 `.claude/skills` |
| `--force` | 覆盖目标目录里不是本脚本装的同名 skill |

更新：`git pull && ./install.sh`。复制模式重新安装会清掉运行时里的 npm 依赖和探测结果，要出成品时再运行一次 `--render-deps`。

`--render-deps` 结束时会提示一步看图验证：在 Claude Code 里让 Claude 打开探测图片、写下看到的内容，再运行 `record_probe.py`。之后运行 `python3 ~/.claude/skills/_allen-runtime/tools/doctor.py`，全部"通过"才能出正式报告。

装好后打开 Claude Code，直接说要做什么即可（见文末“怎么用”）。

## 2. Claude Code 网页版（云端）

云端每次开新会话都是一台新机器，装好的东西不会保留，所以要在**云端环境的 setup script** 里每次自动安装：

1. 在 claude.ai/code 的环境设置里新建一个云端环境（Add cloud environment）。
2. Setup script 填：

   ```bash
   git clone --depth 1 https://github.com/allenwy109/Allen-skills.git /tmp/Allen-skills
   /tmp/Allen-skills/install.sh
   ```

   正式报告需要的依赖（`--render-deps`）目前只支持 macOS；云端要出成品，需在 setup script 里自行安装 Poppler、Tesseract、Pandoc、LibreOffice、Chrome 和 Node 依赖，再用 `doctor.py` 检查。
3. 网络设置要允许访问 GitHub（下载本仓库）；做联网核实还要允许访问一般网站。

这条路目前**还没有实际跑过**。

## 3. claude.ai 聊天（网页、桌面、手机 App）

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

## 4. Agent SDK（自建应用）

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

## 5. Claude API

可以通过 Skills API（`/v1/skills`）上传，但 skill 的运行环境不能联网、不能安装包，核实和正式报告都做不了。除非另有需要，不建议用这种方式。

---

## 怎么用

装好后直接说要做什么，router 会判断场景和深度：

| 想做的事 | 可以这样说 |
|---|---|
| 分析一家企业 | “帮我分析一下 XX 公司，我们在考虑和它合作。” |
| 研究一个话题 | “研究一下 2026 年国内储能行业，值不值得进？” |
| 评审 BP | “评审这份 BP。”（附文件） |
| 个人问题 | “我总是拖延，怎么办？” |
| 只用一个方法 | “用 SWOT 分析一下……”“这个问题该用什么框架？” |
| 只核实 | “帮我核实一下这篇文章里的数据。” |

深度：默认 L2（完整流程、3 个审查者：事实核查员、红队、成品审查员；交正式报告）。说“简单说说”是 L1（对话里直接回答）；说“深入分析”是 L3（5 个审查者，研究和尽调做得更深，研究包封包）。深度的唯一标准在 router 第 2 节。

L2、L3 会在当前目录下建 `work/<日期>-<主题>/` 文件夹，里面是每一步的交接文件；交付物在 `08_deliverables/`，是否完成以 `08_deliverables/acceptance.json` 为准。

## 检查安装是否成功

- Claude Code：问一句“列出你能用的 skill”，应该能看到 `router`、`core-*`、`lib-*`、`scene-*`、`out-*`。
- 出成品的依赖：`python3 ~/.claude/skills/_allen-runtime/tools/doctor.py`。
- 维护者：`python3 tools/validate.py` 检查仓库结构；`tools/selftest.sh` 跑全部测试。

参考：[Agent Skills 概览](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/)、[Agent SDK 中的 skills](https://code.claude.com/docs/en/agent-sdk/skills)。
