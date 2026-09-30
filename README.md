# Allen 的 Skills

这个仓库收集我的 Claude skills，每个 skill 一个目录。

## 安装

把需要的 skill 目录复制到 `~/.claude/skills/` 下即可，例如：

```bash
cp -R consulting-analysis ~/.claude/skills/
```

## 目录

| Skill | 用途 |
|---|---|
| [consulting-analysis](consulting-analysis/) | 站在管理咨询顾问的角度诊断企业：战略、行业竞争、增长、业务组合、利润、定价、并购、组织诊断等，并写成结构化汇报。28 张方法卡片。 |
| [management-toolkit](management-toolkit/) | 企业内部管理：目标设定、计划分工、持续改进、根因分析、复盘、带团队、组织变革、会议讨论。24 张方法卡片。 |
| [personal-effectiveness](personal-effectiveness/) | 个人效率与自我提升：时间与优先级、拖延与专注、习惯、决策、学习、情绪与精力、职业发展、个人表达。21 张方法卡片。 |

每个 skill 的结构：

```
<skill>/
├── SKILL.md                    选法入口：什么问题用什么方法
└── references/
    ├── method-index.md         方法清单：适用、不适用、出处
    └── methods/                方法卡片：步骤、模板、常见误用
```
