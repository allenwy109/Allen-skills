#!/usr/bin/env python3
"""检查 skill 仓库的结构是否完整。

用法：python3 tools/validate.py
检查项：
1. 每个 skill 目录有 SKILL.md，frontmatter 的 name 和目录名一致，description 不为空且不超过 1024 字。
2. SKILL.md 和 references 里出现的 ../<skill>/ 引用，都指向本仓库的 skill。
3. 每张方法卡片都有必备的几节，且在本库的 method-index.md 里被登记。
4. 方法库 SKILL.md 的选法表是四列（情况、首选、前提、换用）。
5. vendor/ 下的引擎与 vendor.lock 一致，且没有残留的 SKILL.md。
6. tools/lib/schema/ 下的 schema 文件通过自检；core-evidence 文档里用反引号写出的字段名和枚举值都在 ledger schema 里。
7. 每个 allen-* 应用都有 app.json 及 Claude/Codex 入口。
发现错误时以非零状态退出。
"""
import pathlib
import json
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
CARD_SECTIONS = ["## 它解决什么问题", "## 什么时候换用别的", "## 前提与不能推出什么", "## 输出模板", "## 常见误用"]

errors, warnings = [], []

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from tools import report_capabilities
try:
    from tools import report_release
except ImportError:
    report_release = None

for e in report_capabilities.check(ROOT):
    errors.append("report capabilities：" + e)
if (ROOT / "references" / "report-output-release.json").is_file():
    if report_release is None:
        errors.append("report release：缺少 tools/report_release.py")
    else:
        for e in report_release.check(ROOT):
            errors.append("report release：" + e)


skills = sorted(p.parent for p in ROOT.glob("*/SKILL.md"))
names = {p.name for p in skills}
known = names

for s in skills:
    text = (s / "SKILL.md").read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        errors.append(f"{s.name}/SKILL.md：缺少 frontmatter")
        continue
    fm = m.group(1)
    name = re.search(r"^name:\s*(.+)$", fm, re.M)
    desc = re.search(r"^description:\s*(.+)$", fm, re.M)
    if not name or name.group(1).strip() != s.name:
        errors.append(f"{s.name}/SKILL.md：name 和目录名不一致")
    if not desc or not desc.group(1).strip():
        errors.append(f"{s.name}/SKILL.md：description 为空")
    elif len(desc.group(1).strip()) > 1024:
        errors.append(f"{s.name}/SKILL.md：description 超过 1024 字")

    for f in [s / "SKILL.md", *s.glob("references/**/*.md")]:
        for ref in re.findall(r"\.\./([a-z0-9-]+)/", f.read_text(encoding="utf-8")):
            if ref not in known:
                errors.append(f"{f.relative_to(ROOT)}：引用了不存在的 skill ../{ref}/")

    # 本 skill 内部的相对路径引用（references/、assets/）要存在
    for rel in re.findall(r"`((?:references|assets)/[^`*]+?\.md)`", text):
        if not (s / rel).exists():
            errors.append(f"{s.name}/SKILL.md：引用的文件不存在：{rel}")

deck = ROOT / "out-deck"
if deck in skills:
    wrapper = deck / "scripts" / "out_deck.py"
    if not wrapper.is_file():
        errors.append("out-deck：缺少 scripts/out_deck.py")
    else:
        source = wrapper.read_text(encoding="utf-8")
        for command in ("init", "refresh", "plan", "step", "finish", "capabilities"):
            if f'"{command}"' not in source:
                errors.append(f"out-deck：wrapper 缺少 {command} 生命周期入口")
    skill_text = (deck / "SKILL.md").read_text(encoding="utf-8")
    for item in ("chart-plan", "layout-plan", "module-fill-plan", "representatives", "production", "delivery"):
        if item not in skill_text:
            errors.append(f"out-deck/SKILL.md：缺少 {item} 清单说明")

for app in sorted(s for s in skills if s.name.startswith("allen-")):
    required = {
        "应用元数据": app / "assets" / "app.json",
        "Claude 入口": ROOT / "commands" / "claude" / f"{app.name}.md",
        "Codex 入口": ROOT / "commands" / "codex" / f"{app.name}.md",
    }
    for label, path in required.items():
        if not path.is_file():
            errors.append(f"{app.name}：缺少 {label}：{path.relative_to(ROOT)}")
    meta_path = required["应用元数据"]
    if meta_path.is_file():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as err:
            errors.append(f"{meta_path.relative_to(ROOT)}：无效 JSON：{err}")
        else:
            if meta.get("id") != app.name:
                errors.append(f"{meta_path.relative_to(ROOT)}：id 必须等于 {app.name}")
            scene = meta.get("scene")
            if scene not in known:
                errors.append(f"{meta_path.relative_to(ROOT)}：scene 指向不存在的 skill {scene}")
            for field in ("title", "report_title"):
                if not isinstance(meta.get(field), str) or not meta[field].strip():
                    errors.append(f"{meta_path.relative_to(ROOT)}：{field} 必须是非空字符串")

for lib in [s for s in skills if s.name.startswith("lib-")]:
    index = (lib / "references" / "method-index.md").read_text(encoding="utf-8")
    for card in sorted((lib / "references" / "methods").glob("*.md")):
        body = card.read_text(encoding="utf-8")
        for sec in CARD_SECTIONS:
            if sec not in body:
                errors.append(f"{card.relative_to(ROOT)}：缺少“{sec[3:]}”一节")
        if f"methods/{card.name}" not in index:
            errors.append(f"{card.relative_to(ROOT)}：没有在 method-index.md 里登记")
        if "## 出处" not in body:
            warnings.append(f"{card.relative_to(ROOT)}：没有“出处”一节")
    skill_text = (lib / "SKILL.md").read_text(encoding="utf-8")
    for header in re.findall(r"^\|([^\n]*)\|\n\|[-| ]+\|", skill_text, re.M):
        cols = [c.strip() for c in header.split("|")]
        if len(cols) != 4 or cols[2] != "前提" or cols[3] != "换用":
            errors.append(f"{lib.name}/SKILL.md：选法表不是“情况 | 首选 | 前提 | 换用”四列：{header.strip()}")

vendor_dir = ROOT / "vendor"
if vendor_dir.is_dir():
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from tools import vendor_sync

    for e in vendor_sync.check(vendor_dir):
        errors.append("vendor：" + e)

schema_dir = ROOT / "tools" / "lib" / "schema"
if schema_dir.is_dir():
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from tools.lib import schema_check

    required_schemas = {
        "research-coverage.schema.json",
        "skill-usage.schema.json",
        "review-closure.schema.json",
        "research-handoff.schema.json",
    }
    for name in sorted(required_schemas):
        if not (schema_dir / name).is_file():
            errors.append(f"tools/lib/schema/{name}：缺少 consulting project schema")

    for f in sorted(schema_dir.glob("*.schema.json")):
        for e in schema_check.self_check(schema_check.load(f)):
            errors.append(f"{f.relative_to(ROOT)}：{e}")
    ledger_schema = schema_check.load("ledger.schema.json")
    vocabulary = {v for e in ledger_schema["enums"].values() for v in e["values"]}
    vocabulary |= {k for t in ledger_schema["tables"].values() for k in t["fields"]}
    vocabulary |= set(ledger_schema["tables"])
    vocabulary |= {"init", "check", "render", "merge"}  # ledger.py 的子命令
    for doc in [ROOT / "core-evidence" / "SKILL.md", *sorted((ROOT / "core-evidence" / "references").glob("*.md"))]:
        for token in re.findall(r"`([a-z][a-z_]*)`", doc.read_text(encoding="utf-8")):
            if token not in vocabulary:
                errors.append(f"{doc.relative_to(ROOT)}：`{token}` 不是 ledger schema 里的字段、表名或枚举值")

for w in warnings:
    print("提示：" + w)
for e in errors:
    print("错误：" + e)
cards = sum(len(list((s / "references" / "methods").glob("*.md"))) for s in skills if s.name.startswith("lib-"))
print(f"共 {len(skills)} 个 skill，{cards} 张方法卡片；错误 {len(errors)} 个，提示 {len(warnings)} 个。")
sys.exit(1 if errors else 0)
