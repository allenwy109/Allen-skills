#!/usr/bin/env python3
"""把本仓库的每个 skill 打成一个 zip，用于上传到 claude.ai（网页、桌面、手机 App）。

用法：python3 tools/build-zips.py [输出目录，默认 dist/]
每个 zip 里是一个以 skill 名命名的文件夹，里面有 SKILL.md 和它的 references、assets、scripts。
不打包：out-*（依赖本机的渲染引擎、Node 和 Chrome）和运行时 _allen-runtime；缓存文件（__pycache__、点文件）也不打包。
core-* 的脚本依赖运行时里的 tools/lib，上传到 claude.ai 后只能按文档手工执行流程，不能运行脚本。
"""
import pathlib
import sys
import zipfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
out = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "dist"
out.mkdir(parents=True, exist_ok=True)

count = 0
for skill_md in sorted(ROOT.glob("*/SKILL.md")):
    skill = skill_md.parent
    if skill.name.startswith(("out-", "_")):
        continue
    target = out / f"{skill.name}.zip"
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(skill.rglob("*")):
            rel = f.relative_to(skill)
            if f.is_file() and not any(part.startswith(".") or part == "__pycache__" for part in rel.parts):
                z.write(f, pathlib.Path(skill.name) / f.relative_to(skill))
    count += 1
    print(f"{target.relative_to(ROOT) if target.is_relative_to(ROOT) else target}")
print(f"共 {count} 个 zip，输出到 {out}")
