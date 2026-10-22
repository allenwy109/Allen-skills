# 架构

## 为什么这样分层

旧版是三个大而全的 skill，每个都复制了一遍完整流程。问题有两个：选方法靠“问法像哪一行”，不检查前提；整个流程没有事实核实。新版按功能拆开，流程只写一份，选方法和核实各成一个 skill，并加了独立审查。

```
入口        router：判断场景，定深度（L1 快答 / L2 标准 / L3 深度），建任务文件夹
             │
场景层      scene-company   scene-topic   scene-bp-review   scene-personal
             │  只编排：按什么顺序调哪些能力、交付什么、哪些关口必须过
             │
能力层      core-framing → core-method-select → （按卡片分析）→ core-synthesis
                               │                   │
                               │               core-evidence（检索与核实，全程可调）
                               │
质量层                     core-review（独立子代理审查）
             │
方法库      lib-consulting   lib-management   lib-personal（卡片 + 选法表，不带流程）
             │
交付与研究  zerox-storyline、zerox-consulting-report-forge、zerox-thinkcell-charts、zerox-onepager
            zerox-deep-research、zerox-due-diligence（install.sh 安装，固定版本）
```

## 三条边界

1. **方法库不带流程。** 只回答“有哪些方法、什么时候能用、怎么用对”。
2. **能力 skill 只管一件事，可以单独用。** 例如只想核实一篇文章，就只调 core-evidence。
3. **场景 skill 只编排，不重复规则。** 系统提示词只是一层薄壳：角色 + 指向场景 skill + 不可跳过的规则（见 `router/references/system-prompts.md`）。

## 两道关口

| 关口 | 在哪 | 查什么 |
|---|---|---|
| 选方法关口 | core-method-select | 子问题画像；方法前提是否满足（不满足就补信息或降级，不用推断填满）；预演产出能否回答子问题；为什么不用相邻方法 |
| 核实关口 | core-evidence 第 6 节，core-synthesis 开始前 | 影响结论的事实是否已核实；未核实的改写成“如果……则……”并列入待确认问题 |

## 交接文件

skill 之间不靠对话记忆传递，而是通过任务文件夹里的固定文件。换一个 skill、重做一步、另开一个审查者，都不用重讲一遍。

```
work/<日期>-<主题>/
├── 00_brief.md          router
├── 01_issue-tree.md     core-framing
├── 02_method-plan.md    core-method-select
├── 03_evidence.md       core-evidence（编号 E1、E2……；zerox 的来源编号原样保留）
├── 04_analysis/         按卡片做的分析
├── 05_review-log.md     core-review
├── 06_synthesis.md      core-synthesis
└── 07_deliverables/     交付物
```

L1 快答不建文件夹，内容直接写在回答里。

## 审查

| 角色 | 只查什么 | L2 | L3 |
|---|---|---|---|
| 事实核查员 | 影响结论的事实，独立联网重查 | 开 | 开 |
| 红队 | 最强反对理由、其他解释、维持现状基准、强词 | 开 | 开 |
| 方法审查员 | 方法是否选对、前提是否满足、常见误用 | — | 开 |
| 决策者视角 | 一页内能否看懂、能否执行 | — | 开 |

审查者必须是没参与写作的独立子代理。没有子代理能力的环境降级为按清单自审，并在报告里写明“未经独立审查”。

## 第三方依赖

zerox skill 按 `zerox.lock` 的固定 commit 安装。场景 skill 只通过交接文件使用它们（把我们核实过的内容交给它们排版），不依赖它们的内部实现；zerox 升级或替换时只改交接那一层。未安装时，各场景降级为 Markdown 交付。

正式报告（zerox-consulting-report-forge）需要 Node.js 20+、Python 3.10+、Chrome 或 Playwright Chromium、Poppler；上游只在 macOS 上完整验证过。

## 后续计划

1. 用 `tests/method-selection-cases.md` 跑一次基线，按结果修选法表。
2. 用 1 到 2 份真实 BP 跑通 scene-bp-review，含正式报告。
3. scene-company、scene-topic 各用 2 个真实案例跑通。
4. 把回退记录和审查记录里反复出现的问题，回写到选法表和卡片的“常见误用”。
