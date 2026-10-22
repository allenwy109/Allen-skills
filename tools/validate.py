#!/usr/bin/env python3
"""检查 skill 仓库的结构是否完整。

用法：python3 tools/validate.py
检查项：
1. 每个 skill 目录有 SKILL.md，frontmatter 的 name 和目录名一致，description 不为空且不超过 1024 字。
2. SKILL.md 和 references 里出现的 ../<skill>/ 引用，都指向本仓库的 skill 或 zerox.lock 里登记的 zerox skill。
3. 每张方法卡片都有必备的几节，且在本库的 method-index.md 里被登记。
4. 方法库 SKILL.md 的选法表是四列（情况、首选、前提、换用）。
发现错误时以非零状态退出。
"""
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
CARD_SECTIONS = ["## 它解决什么问题", "## 什么时候换用别的", "## 前提与不能推出什么", "## 输出模板", "## 常见误用"]

errors, warnings = [], []


def zerox_skills():
    text = (ROOT / "zerox.lock").read_text(encoding="utf-8")
    m = re.search(r'^ZEROX_SKILLS="([^"]*)"', text, re.M)
    return set(m.group(1).split()) if m else set()


skills = sorted(p.parent for p in ROOT.glob("*/SKILL.md"))
names = {p.name for p in skills}
known = names | zerox_skills()

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

for w in warnings:
    print("提示：" + w)
for e in errors:
    print("错误：" + e)
cards = sum(len(list((s / "references" / "methods").glob("*.md"))) for s in skills if s.name.startswith("lib-"))
print(f"共 {len(skills)} 个 skill，{cards} 张方法卡片；错误 {len(errors)} 个，提示 {len(warnings)} 个。")
sys.exit(1 if errors else 0)
