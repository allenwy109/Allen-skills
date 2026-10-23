#!/usr/bin/env python3
"""把 zerox 的三个 Apache-2.0 引擎按固定 commit 复制到 vendor/，并维护 vendor.lock。

用法（在仓库根目录）：
  python3 tools/vendor_sync.py sync [--repo URL] [--cache DIR] [--vendor DIR]
  python3 tools/vendor_sync.py check [--vendor DIR]

sync：拉取 vendor.config.json 固定的 commit，按配置复制三个引擎（跳过 exclude），
      SKILL.md 改名为 UPSTREAM-SKILL.md，依次打 vendor/patches/*.patch，最后重写 vendor.lock。
      注意：sync 会删掉 vendor/<引擎> 下原有的全部内容（包括 node_modules），之后要重新运行 ./install.sh --render-deps。
check：按 vendor.lock 核对每个文件的哈希；报告缺失、被改动、未登记的文件，以及残留的 SKILL.md。
       运行时生成物（vendor.lock 的 generated 列表）不参与核对。
"""
import argparse
import fnmatch
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
VENDOR = ROOT / "vendor"
ALWAYS_EXCLUDE = [".git/", ".installed-by-allen-skills"]
DEFAULT_CACHE = pathlib.Path(os.environ.get("XDG_CACHE_HOME") or pathlib.Path.home() / ".cache") / "allen-skills" / "zerox-skills"


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def matches(rel, patterns):
    """rel 是相对路径（用 / 分隔）。
    以 / 结尾的模式表示目录：不含 / 的（如 node_modules/）匹配任意一级目录名；含 / 的（如 docs/showcase/）只匹配路径前缀。
    其余模式按 fnmatch 匹配整个相对路径。"""
    parts = rel.split("/")
    for p in patterns:
        if p.endswith("/"):
            d = p[:-1]
            if "/" in d:
                if rel.startswith(p):
                    return True
            elif d in parts[:-1]:
                return True
        elif fnmatch.fnmatch(rel, p):
            return True
    return False


def fetch(repo, commit, cache):
    cache = pathlib.Path(cache)
    cache.mkdir(parents=True, exist_ok=True)
    git = ["git", "-C", str(cache)]
    if not (cache / ".git").is_dir():
        subprocess.run(git + ["init", "-q"], check=True)
        subprocess.run(git + ["remote", "add", "origin", repo], check=True)
    else:
        subprocess.run(git + ["remote", "set-url", "origin", repo], check=True)
    head = subprocess.run(git + ["rev-parse", "-q", "--verify", "HEAD"], capture_output=True, text=True).stdout.strip()
    if head != commit:
        env = dict(os.environ, GIT_LFS_SKIP_SMUDGE="1")
        subprocess.run(git + ["fetch", "-q", "--depth", "1", "origin", commit], check=True, env=env)
        subprocess.run(git + ["checkout", "-q", "--force", "FETCH_HEAD"], check=True, env=env)
    return cache


def copy_engine(src, dst, excludes):
    src, dst = pathlib.Path(src), pathlib.Path(dst)
    if not src.is_dir():
        raise SystemExit(f"上游目录不存在：{src}")
    if dst.exists():
        shutil.rmtree(dst)
    for path in sorted(src.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(src).as_posix()
        if matches(rel, ALWAYS_EXCLUDE + list(excludes)):
            continue
        out = dst / ("UPSTREAM-SKILL.md" if rel == "SKILL.md" else rel)
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, out)


def apply_patches(vendor):
    """补丁路径写成 a/<引擎>/<文件>。用 patch 而不是 git apply：
    vendor/ 在 git 仓库的子目录里时，git apply 会按仓库根目录解析路径，并悄悄跳过子目录外的改动。"""
    applied = []
    for patch in sorted((pathlib.Path(vendor) / "patches").glob("*.patch")):
        # -r - ：打不上时不留下 .rej 文件；失败后修好补丁，重新运行 sync 即可恢复
        subprocess.run(["patch", "-p1", "-N", "-t", "-s", "-r", "-", "-i", str(patch)], cwd=vendor, check=True)
        applied.append({"name": patch.name, "sha256": sha256(patch)})
    return applied


def engine_files(engine_dir, generated):
    files = {}
    for p in sorted(pathlib.Path(engine_dir).rglob("*")):
        if p.is_file():
            rel = p.relative_to(engine_dir).as_posix()
            if not matches(rel, generated):
                files[rel] = sha256(p)
    return files


def sync(cfg, vendor, cache, repo=None):
    vendor = pathlib.Path(vendor)
    src_root = fetch(repo or cfg["repo"], cfg["commit"], cache)
    for name, spec in cfg["engines"].items():
        copy_engine(src_root / spec["upstream"], vendor / name, spec.get("exclude", []))
    patches = apply_patches(vendor)
    generated = cfg.get("generated", [])
    lock = {
        "repo": cfg["repo"],
        "commit": cfg["commit"],
        "generated": generated,
        "patches": patches,
        "engines": {
            name: {"upstream": spec["upstream"], "files": engine_files(vendor / name, generated)}
            for name, spec in cfg["engines"].items()
        },
    }
    (vendor / "vendor.lock").write_text(json.dumps(lock, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return lock


def check(vendor):
    vendor = pathlib.Path(vendor)
    lock_path = vendor / "vendor.lock"
    if not lock_path.is_file():
        return [f"缺少 {lock_path}"]
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    generated = lock.get("generated", [])
    errors = []
    current = [{"name": p.name, "sha256": sha256(p)} for p in sorted((vendor / "patches").glob("*.patch"))]
    if current != lock.get("patches", []):
        errors.append("补丁与 vendor.lock 不一致，请重新运行 sync")
    for d in sorted(p for p in vendor.iterdir() if p.is_dir()):
        if d.name != "patches" and d.name not in lock["engines"]:
            errors.append(f"未登记的引擎目录：{d.name}")
    for name, eng in sorted(lock["engines"].items()):
        d = vendor / name
        if (d / "SKILL.md").exists():
            errors.append(f"{name}/SKILL.md 不应存在（上游的 SKILL.md 应改名为 UPSTREAM-SKILL.md）")
        for rel, digest in sorted(eng["files"].items()):
            p = d / rel
            if not p.is_file():
                errors.append(f"缺少文件：{name}/{rel}")
            elif sha256(p) != digest:
                errors.append(f"文件被改动：{name}/{rel}")
        actual = set(engine_files(d, generated)) if d.is_dir() else set()
        for rel in sorted(actual - set(eng["files"])):
            if rel != "SKILL.md":
                errors.append(f"未登记的文件：{name}/{rel}")
    return errors


def main(argv=None):
    ap = argparse.ArgumentParser(description="同步或检查 vendor/ 下的引擎")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sync")
    s.add_argument("--repo", help="改用其他上游地址（例如自己的 fork）")
    s.add_argument("--cache", default=str(DEFAULT_CACHE))
    s.add_argument("--vendor", default=str(VENDOR))
    c = sub.add_parser("check")
    c.add_argument("--vendor", default=str(VENDOR))
    a = ap.parse_args(argv)
    vendor = pathlib.Path(a.vendor)
    if a.cmd == "sync":
        cfg = json.loads((vendor / "vendor.config.json").read_text(encoding="utf-8"))
        lock = sync(cfg, vendor, a.cache, a.repo)
        n = sum(len(e["files"]) for e in lock["engines"].values())
        print(f"已同步 {len(lock['engines'])} 个引擎、{n} 个文件 @ {lock['commit'][:7]}；补丁 {len(lock['patches'])} 个")
        print("下一步：重新运行 ./install.sh --render-deps（sync 会清掉引擎目录下的 npm 依赖），再运行 tools/selftest.sh 跑引擎自带测试")
        return 0
    errors = check(vendor)
    for e in errors:
        print("错误：" + e)
    print("vendor 检查通过" if not errors else f"vendor 检查失败：{len(errors)} 个错误")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
