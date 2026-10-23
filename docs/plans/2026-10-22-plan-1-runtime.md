# 计划 1：渲染运行环境 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 zerox 的三个 Apache-2.0 引擎按固定 commit 并入 `vendor/`，并在本机装好它们运行所需的全部依赖，由 doctor 和自检证明能跑通。

**Architecture:**
- `tools/vendor_sync.py` 负责从上游复制引擎、维护 `vendor/vendor.lock`。
- `tools/lib/runtime.py` 是所有脚本找引擎和虚拟环境的唯一入口。
- `install.sh` 新增安装 `_allen-runtime`（复制或软链接）和 `--render-deps`（系统工具、Python 虚拟环境、npm 依赖、字体、能力探测任务）。
- `tools/doctor.py` 逐项检查环境，`tools/record_probe.py` 记录看图验证的结果，`tools/selftest.sh` 跑单元测试、结构检查和三个引擎自带的测试。

**Tech Stack:** Python 3 标准库（unittest、subprocess、hashlib）、bash、git、patch、rsync、Homebrew、npm、Playwright。

**依据：** 设计 §6.1、§9、§11、§12 第 1 步；共用约定见 `2026-10-22-zerox-absorption-roadmap.md`。

**本计划不做：**
- 不删除 zerox.lock，也不停止安装 zerox：场景 skill 目前还在调用 zerox，要到计划 8 才切换。`--no-zerox`、`--remove-old` 清理 `zerox-*`、build-zips.py 排除 out-* 和 `_allen-runtime`，也都放到计划 8。
- 不改动 `~/.claude/skills`。

---

## 文件结构

| 文件 | 职责 |
|---|---|
| `vendor/vendor.config.json`（新建） | 上游仓库、固定 commit、三个引擎的上游目录、排除项、运行时生成物 |
| `vendor/vendor.lock`（由脚本生成） | 每个引擎每个文件的 sha256，以及已打的补丁 |
| `vendor/patches/`（新建，起始为空） | 补丁文件，起始 0 个 |
| `vendor/report-forge/`、`vendor/thinkcell-charts/`、`vendor/onepager/`（由脚本生成） | 引擎代码；上游 SKILL.md 改名为 UPSTREAM-SKILL.md |
| `tools/__init__.py`、`tools/lib/__init__.py`、`tools/tests/__init__.py`（新建，空文件） | 让 `tools.*` 可以作为包导入 |
| `tools/vendor_sync.py`（新建） | sync 与 check |
| `tools/lib/runtime.py`（新建） | 解析运行时根目录、引擎目录、虚拟环境 Python |
| `tools/requirements-render.txt`（新建） | 虚拟环境要装的包 |
| `tools/doctor.py`（新建） | 环境检查 |
| `tools/record_probe.py`（新建） | 能力探测验证与记录 |
| `tools/selftest.sh`（新建） | 一条命令跑完全部自检 |
| `tools/tests/test_vendor_sync.py`、`test_runtime.py`、`test_install.py`、`test_doctor.py`、`test_record_probe.py`、`test_validate.py`（新建） | 单元测试 |
| `.gitattributes`（新建） | vendor 下的文件不做换行转换 |
| `install.sh`（修改） | 安装 `_allen-runtime`、`--render-deps`、`--forge-deps` 改为别名 |
| `tools/validate.py`（修改） | 增加 vendor 检查 |
| `.gitignore`（修改） | 忽略运行时生成物 |
| `.github/workflows/validate.yml`（修改） | 增加单元测试 |

所有命令都在仓库根目录 `~/Repos/Allen-skills` 下执行。

---

### Task 1: 包结构与 vendor 配置

**Files:**
- Create: `tools/__init__.py`, `tools/lib/__init__.py`, `tools/tests/__init__.py`（三个空文件）
- Create: `vendor/vendor.config.json`
- Create: `vendor/patches/.gitkeep`（空文件）
- Create: `.gitattributes`
- Modify: `.gitignore`

- [ ] **Step 1: 建空的包文件和补丁目录**

```bash
mkdir -p tools/lib tools/tests vendor/patches
: > tools/__init__.py; : > tools/lib/__init__.py; : > tools/tests/__init__.py; : > vendor/patches/.gitkeep
```

- [ ] **Step 2: 写 `vendor/vendor.config.json`**

```json
{
 "repo": "https://github.com/ZeroxZhang/zerox-skills.git",
 "commit": "ee1f980c8dd7c53408e1a05a084229e6ec03c660",
 "generated": ["node_modules/", ".font-venv/", "__pycache__/", ".pytest_cache/", ".venv/", "renders/", "*.DS_Store", "*.pyc"],
 "engines": {
  "report-forge": {"upstream": "zerox-consulting-report-forge", "exclude": ["docs/showcase/"]},
  "thinkcell-charts": {"upstream": "zerox-thinkcell-charts", "exclude": []},
  "onepager": {"upstream": "zerox-onepager", "exclude": ["Onepager_产品横纵分析报告.*", "onepager-A4-B9-T4-20260531.*"]}
 }
}
```

排除项的理由：
- `docs/showcase/`（7.4 MB）是展示样例，脚本和测试都不引用；
- onepager 根目录下的样例报告和样例海报，脚本和测试也不引用。

字体、示例、测试都保留。

- [ ] **Step 3: 在 `.gitignore` 末尾追加运行时生成物**

```
vendor/*/node_modules/
vendor/*/.font-venv/
__pycache__/
.probe-task/
.probe.json
```

- [ ] **Step 4: 写 `.gitattributes`**

上游有些文件混用 CRLF 和 LF。为了保证哈希不会因为换行转换而变化，vendor 下的文件一律按二进制原样存放：

```
vendor/** -text
```

- [ ] **Step 5: 提交**

```bash
git add tools/__init__.py tools/lib/__init__.py tools/tests/__init__.py vendor/vendor.config.json vendor/patches/.gitkeep .gitignore .gitattributes
git -c user.name="allenwy109" -c user.email="51287374+allenwy109@users.noreply.github.com" commit -m "chore(vendor): add vendor config and package skeleton

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: vendor_sync —— 路径匹配与复制

**Files:**
- Create: `tools/vendor_sync.py`
- Test: `tools/tests/test_vendor_sync.py`

- [ ] **Step 1: 写失败的测试**

`tools/tests/test_vendor_sync.py`：

```python
import json
import pathlib
import subprocess
import tempfile
import unittest

from tools import vendor_sync


def git(cwd, *args):
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True)


def make_upstream(root):
    """建一个本地上游仓库：两个引擎目录，含要排除的文件。返回 (仓库路径, commit)。"""
    repo = root / "upstream"
    (repo / "eng-a" / "docs" / "showcase").mkdir(parents=True)
    (repo / "eng-a" / "SKILL.md").write_text("---\nname: eng-a\n---\n", encoding="utf-8")
    (repo / "eng-a" / "a.txt").write_text("alpha\n", encoding="utf-8")
    (repo / "eng-a" / "docs" / "guide.md").write_text("guide\n", encoding="utf-8")
    (repo / "eng-a" / "docs" / "showcase" / "big.bin").write_bytes(b"x" * 10)
    (repo / "eng-b").mkdir()
    (repo / "eng-b" / "b.txt").write_text("beta\n", encoding="utf-8")
    (repo / "eng-b" / "sample.pdf").write_bytes(b"%PDF")
    git(repo, "init", "-q")
    git(repo, "config", "uploadpack.allowReachableSHA1InWant", "true")
    git(repo, "add", "-A")
    git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "init")
    commit = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    return repo, commit


def make_config(repo, commit):
    return {
        "repo": repo.as_uri(),
        "commit": commit,
        "generated": ["node_modules/", "__pycache__/"],
        "engines": {
            "a": {"upstream": "eng-a", "exclude": ["docs/showcase/"]},
            "b": {"upstream": "eng-b", "exclude": ["sample.*"]},
        },
    }


class MatchesTest(unittest.TestCase):
    def test_directory_pattern_without_slash_matches_any_component(self):
        self.assertTrue(vendor_sync.matches("x/__pycache__/m.pyc", ["__pycache__/"]))
        self.assertTrue(vendor_sync.matches("node_modules/p/index.js", ["node_modules/"]))

    def test_directory_pattern_with_slash_matches_prefix_only(self):
        self.assertTrue(vendor_sync.matches("docs/showcase/a.png", ["docs/showcase/"]))
        self.assertFalse(vendor_sync.matches("other/docs/showcase/a.png", ["docs/showcase/"]))

    def test_glob_pattern(self):
        self.assertTrue(vendor_sync.matches("sample.pdf", ["sample.*"]))
        self.assertFalse(vendor_sync.matches("b.txt", ["sample.*"]))


class SyncTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = pathlib.Path(self.tmp.name)
        self.repo, self.commit = make_upstream(root)
        self.cfg = make_config(self.repo, self.commit)
        self.vendor = root / "vendor"
        (self.vendor / "patches").mkdir(parents=True)
        self.cache = root / "cache"

    def tearDown(self):
        self.tmp.cleanup()

    def test_sync_copies_renames_excludes_and_locks(self):
        lock = vendor_sync.sync(self.cfg, self.vendor, self.cache)
        a = self.vendor / "a"
        self.assertTrue((a / "UPSTREAM-SKILL.md").is_file())
        self.assertFalse((a / "SKILL.md").exists())
        self.assertTrue((a / "docs" / "guide.md").is_file())
        self.assertFalse((a / "docs" / "showcase").exists())
        self.assertFalse((self.vendor / "b" / "sample.pdf").exists())
        self.assertEqual(lock["commit"], self.commit)
        self.assertEqual(set(lock["engines"]["a"]["files"]), {"UPSTREAM-SKILL.md", "a.txt", "docs/guide.md"})
        self.assertEqual(lock["engines"]["a"]["files"]["a.txt"], vendor_sync.sha256(a / "a.txt"))
        on_disk = json.loads((self.vendor / "vendor.lock").read_text(encoding="utf-8"))
        self.assertEqual(on_disk, lock)

    def test_check_passes_after_sync(self):
        vendor_sync.sync(self.cfg, self.vendor, self.cache)
        self.assertEqual(vendor_sync.check(self.vendor), [])

    def test_check_reports_modified_missing_extra_and_skill_md(self):
        vendor_sync.sync(self.cfg, self.vendor, self.cache)
        (self.vendor / "a" / "a.txt").write_text("changed\n", encoding="utf-8")
        (self.vendor / "b" / "b.txt").unlink()
        (self.vendor / "b" / "extra.txt").write_text("x", encoding="utf-8")
        (self.vendor / "a" / "SKILL.md").write_text("x", encoding="utf-8")
        errors = "\n".join(vendor_sync.check(self.vendor))
        self.assertIn("文件被改动：a/a.txt", errors)
        self.assertIn("缺少文件：b/b.txt", errors)
        self.assertIn("未登记的文件：b/extra.txt", errors)
        self.assertIn("a/SKILL.md 不应存在", errors)

    def test_check_ignores_generated_files(self):
        vendor_sync.sync(self.cfg, self.vendor, self.cache)
        nm = self.vendor / "a" / "node_modules" / "p"
        nm.mkdir(parents=True)
        (nm / "index.js").write_text("x", encoding="utf-8")
        self.assertEqual(vendor_sync.check(self.vendor), [])

    def test_patches_are_applied_and_recorded(self):
        patch = (
            "--- a/a/a.txt\n"
            "+++ b/a/a.txt\n"
            "@@ -1 +1 @@\n"
            "-alpha\n"
            "+alpha patched\n"
        )
        (self.vendor / "patches" / "0001-test.patch").write_text(patch, encoding="utf-8")
        lock = vendor_sync.sync(self.cfg, self.vendor, self.cache)
        self.assertEqual((self.vendor / "a" / "a.txt").read_text(encoding="utf-8"), "alpha patched\n")
        self.assertEqual([p["name"] for p in lock["patches"]], ["0001-test.patch"])
        self.assertEqual(vendor_sync.check(self.vendor), [])

    def test_check_without_lock(self):
        errors = vendor_sync.check(self.vendor)
        self.assertEqual(len(errors), 1)
        self.assertIn("缺少", errors[0])

    def test_missing_upstream_dir_is_an_error(self):
        self.cfg["engines"]["c"] = {"upstream": "eng-missing", "exclude": []}
        with self.assertRaises(SystemExit):
            vendor_sync.sync(self.cfg, self.vendor, self.cache)

    def test_conflicting_patch_is_an_error(self):
        patch = "--- a/a/a.txt\n+++ b/a/a.txt\n@@ -1 +1 @@\n-not the content\n+x\n"
        (self.vendor / "patches" / "0001-bad.patch").write_text(patch, encoding="utf-8")
        with self.assertRaises(subprocess.CalledProcessError):
            vendor_sync.sync(self.cfg, self.vendor, self.cache)

    def test_check_detects_patch_changes_after_sync(self):
        vendor_sync.sync(self.cfg, self.vendor, self.cache)
        (self.vendor / "patches" / "0002-new.patch").write_text("x", encoding="utf-8")
        self.assertIn("补丁与 vendor.lock 不一致", "\n".join(vendor_sync.check(self.vendor)))

    def test_check_detects_unknown_engine_dir(self):
        vendor_sync.sync(self.cfg, self.vendor, self.cache)
        (self.vendor / "stray").mkdir()
        self.assertIn("未登记的引擎目录：stray", "\n".join(vendor_sync.check(self.vendor)))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `python3 -m unittest tools.tests.test_vendor_sync -v`
Expected: 报错 `ImportError: cannot import name 'vendor_sync'`

- [ ] **Step 3: 写 `tools/vendor_sync.py`**

```python
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
```

- [ ] **Step 4: 运行测试，确认通过**

Run: `python3 -m unittest tools.tests.test_vendor_sync -v`
Expected: 13 个测试全部 `ok`。

- [ ] **Step 5: 提交**

```bash
git add tools/vendor_sync.py tools/tests/test_vendor_sync.py
git -c user.name="allenwy109" -c user.email="51287374+allenwy109@users.noreply.github.com" commit -m "feat(vendor): add vendor_sync with lock and check

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: 实际同步三个引擎

**Files:**
- Create（由脚本生成）: `vendor/report-forge/**`, `vendor/thinkcell-charts/**`, `vendor/onepager/**`, `vendor/vendor.lock`

- [ ] **Step 1: 同步**

Run: `python3 tools/vendor_sync.py sync`
Expected: `已同步 3 个引擎、<N> 个文件 @ ee1f980；补丁 0 个`（N 约为 500）

- [ ] **Step 2: 核对结果**

Run:
```bash
python3 tools/vendor_sync.py check
ls vendor/report-forge/UPSTREAM-SKILL.md vendor/report-forge/LICENSE vendor/report-forge/NOTICE vendor/report-forge/THIRD_PARTY_NOTICES.md vendor/thinkcell-charts/LICENSE vendor/thinkcell-charts/NOTICE vendor/onepager/LICENSE.txt
ls vendor/*/SKILL.md 2>/dev/null | wc -l
du -sh vendor
```
Expected:
- `vendor 检查通过`；
- 7 个许可与声明文件都存在；
- SKILL.md 数量为 0；
- 总体积约 34 MB。

- [ ] **Step 3: 提交（这是一次大提交，约 34 MB）**

```bash
git add vendor
git -c user.name="allenwy109" -c user.email="51287374+allenwy109@users.noreply.github.com" commit -m "chore(vendor): import report-forge, thinkcell-charts, onepager @ ee1f980

Apache-2.0 engines from ZeroxZhang/zerox-skills, copied unchanged except
SKILL.md renamed to UPSTREAM-SKILL.md. Licenses and notices kept.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: runtime.py

**Files:**
- Create: `tools/lib/runtime.py`
- Test: `tools/tests/test_runtime.py`

- [ ] **Step 1: 写失败的测试**

`tools/tests/test_runtime.py`：

```python
import pathlib
import tempfile
import unittest
from unittest import mock

from tools.lib import runtime


def make_runtime(root):
    (root / "vendor" / "report-forge").mkdir(parents=True)
    (root / "vendor" / "vendor.lock").write_text("{}", encoding="utf-8")
    return root


class RuntimeRootTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = pathlib.Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_env_override_wins(self):
        rt = make_runtime(self.base / "rt")
        self.assertEqual(runtime.runtime_root(env={"ALLEN_RUNTIME": str(rt)}), rt.resolve())

    def test_invalid_env_override_is_an_error(self):
        with self.assertRaises(runtime.RuntimeNotFound):
            runtime.runtime_root(env={"ALLEN_RUNTIME": str(self.base / "nope")})

    def test_installed_runtime_next_to_skill(self):
        make_runtime(self.base / "skills" / "_allen-runtime")
        skill = self.base / "skills" / "out-report"
        skill.mkdir(parents=True)
        self.assertEqual(runtime.runtime_root(skill_dir=skill, env={}), (self.base / "skills" / "_allen-runtime").resolve())

    def test_falls_back_to_repo_root(self):
        repo = make_runtime(self.base / "repo")
        with mock.patch.object(runtime, "REPO_ROOT", repo):
            self.assertEqual(runtime.runtime_root(env={}), repo.resolve())

    def test_nothing_found(self):
        with mock.patch.object(runtime, "REPO_ROOT", self.base / "empty"):
            with self.assertRaises(runtime.RuntimeNotFound):
                runtime.runtime_root(env={})


class EngineAndVenvTest(unittest.TestCase):
    def test_engine_dir(self):
        with tempfile.TemporaryDirectory() as t:
            rt = make_runtime(pathlib.Path(t))
            d = runtime.engine_dir("report-forge", env={"ALLEN_RUNTIME": str(rt)})
            self.assertEqual(d, (rt / "vendor" / "report-forge").resolve())

    def test_unknown_engine(self):
        with self.assertRaises(ValueError):
            runtime.engine_dir("zerox-deep-research", env={})
        with self.assertRaises(ValueError):
            runtime.engine_path("/rt", "zerox-deep-research")

    def test_engine_path(self):
        self.assertEqual(runtime.engine_path("/rt", "onepager"), pathlib.Path("/rt/vendor/onepager"))

    def test_missing_engine_dir(self):
        with tempfile.TemporaryDirectory() as t:
            rt = make_runtime(pathlib.Path(t))
            with self.assertRaises(runtime.RuntimeNotFound):
                runtime.engine_dir("onepager", env={"ALLEN_RUNTIME": str(rt)})

    def test_venv_python_default_and_override(self):
        self.assertEqual(runtime.venv_python(env={"ALLEN_VENV": "/x/venv"}), pathlib.Path("/x/venv/bin/python"))
        default = runtime.venv_python(env={"HOME": "/home/u"})
        self.assertEqual(default, pathlib.Path("/home/u/.cache/allen-skills/venv/bin/python"))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `python3 -m unittest tools.tests.test_runtime -v`
Expected: `ImportError: cannot import name 'runtime'`

- [ ] **Step 3: 写 `tools/lib/runtime.py`**

```python
"""运行时路径的唯一解析入口（设计 §9）。

运行时根目录（含 vendor/ 和 tools/）的查找顺序：
1. 环境变量 ALLEN_RUNTIME（设置了但无效时直接报错，不往下找）；
2. <skill 目录>/../_allen-runtime（install.sh 安装后的位置）；
3. 本文件所在的仓库根目录（开发时；安装后它就是 _allen-runtime 本身）。
判断标准：目录下存在 vendor/vendor.lock。
"""
import os
import pathlib

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
ENGINES = ("report-forge", "thinkcell-charts", "onepager")
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
SOFFICE_APP = "/Applications/LibreOffice.app/Contents/MacOS/soffice"


class RuntimeNotFound(RuntimeError):
    pass


def engine_path(rt, name):
    """已知运行时根目录时，取某个引擎的目录（不检查是否存在）。"""
    if name not in ENGINES:
        raise ValueError(f"未知引擎：{name}（可选：{'、'.join(ENGINES)}）")
    return pathlib.Path(rt) / "vendor" / name


def _valid(path):
    return (path / "vendor" / "vendor.lock").is_file()


def runtime_root(skill_dir=None, env=None):
    env = os.environ if env is None else env
    override = env.get("ALLEN_RUNTIME")
    if override:
        p = pathlib.Path(override)
        if not _valid(p):
            raise RuntimeNotFound(f"ALLEN_RUNTIME={override} 下没有 vendor/vendor.lock")
        return p.resolve()
    candidates = []
    if skill_dir:
        candidates.append(pathlib.Path(skill_dir).resolve().parent / "_allen-runtime")
    candidates.append(REPO_ROOT)
    for c in candidates:
        if _valid(c):
            return c.resolve()
    raise RuntimeNotFound("找不到运行时（vendor/vendor.lock）：" + "、".join(str(c) for c in candidates) + "。请先运行 ./install.sh")


def engine_dir(name, skill_dir=None, env=None):
    if name not in ENGINES:
        raise ValueError(f"未知引擎：{name}（可选：{'、'.join(ENGINES)}）")
    d = engine_path(runtime_root(skill_dir=skill_dir, env=env), name)
    if not d.is_dir():
        raise RuntimeNotFound(f"引擎目录不存在：{d}")
    return d


def venv_python(env=None):
    env = os.environ if env is None else env
    if env.get("ALLEN_VENV"):
        base = pathlib.Path(env["ALLEN_VENV"])
    else:
        cache = env.get("XDG_CACHE_HOME") or str(pathlib.Path(env.get("HOME") or pathlib.Path.home()) / ".cache")
        base = pathlib.Path(cache) / "allen-skills" / "venv"
    return base / "bin" / "python"
```

- [ ] **Step 4: 运行测试，确认通过**

Run: `python3 -m unittest tools.tests.test_runtime -v`
Expected: 10 个测试全部 `ok`。

- [ ] **Step 5: 提交**

```bash
git add tools/lib/runtime.py tools/tests/test_runtime.py
git -c user.name="allenwy109" -c user.email="51287374+allenwy109@users.noreply.github.com" commit -m "feat(runtime): add runtime path resolver

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: install.sh —— 安装 `_allen-runtime`

**Files:**
- Modify: `install.sh`
- Test: `tools/tests/test_install.py`

- [ ] **Step 1: 写失败的测试**

`tools/tests/test_install.py`：

```python
import pathlib
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]


def install(*args):
    return subprocess.run(["bash", str(ROOT / "install.sh"), "--no-zerox", *args], capture_output=True, text=True)


class InstallRuntimeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.target = pathlib.Path(self.tmp.name) / "skills"

    def tearDown(self):
        self.tmp.cleanup()

    def test_copy_mode_installs_runtime_with_marker(self):
        p = install("--target", str(self.target))
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        rt = self.target / "_allen-runtime"
        self.assertTrue((self.target / "router" / "SKILL.md").is_file())
        self.assertTrue((rt / "vendor" / "vendor.lock").is_file())
        self.assertTrue((rt / "tools" / "lib" / "runtime.py").is_file())
        self.assertTrue((rt / ".installed-by-allen-skills").is_file())
        self.assertFalse(rt.is_symlink())
        check = subprocess.run(["python3", str(rt / "tools" / "vendor_sync.py"), "check"], capture_output=True, text=True)
        self.assertEqual(check.returncode, 0, check.stdout)

    def test_reinstall_is_idempotent(self):
        self.assertEqual(install("--target", str(self.target)).returncode, 0)
        p = install("--target", str(self.target))
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("_allen-runtime", p.stdout)

    def test_link_mode_links_repo_root(self):
        p = install("--link", "--target", str(self.target))
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        rt = self.target / "_allen-runtime"
        self.assertTrue(rt.is_symlink())
        self.assertEqual(rt.resolve(), ROOT.resolve())

    def test_foreign_runtime_dir_is_not_overwritten(self):
        foreign = self.target / "_allen-runtime"
        foreign.mkdir(parents=True)
        (foreign / "mine.txt").write_text("keep", encoding="utf-8")
        p = install("--target", str(self.target))
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertTrue((foreign / "mine.txt").is_file())
        self.assertIn("_allen-runtime（目标已存在且不是本脚本安装的", p.stdout)

    def test_help_lists_render_deps(self):
        p = subprocess.run(["bash", str(ROOT / "install.sh"), "--help"], capture_output=True, text=True)
        self.assertEqual(p.returncode, 0)
        self.assertIn("--render-deps", p.stdout)
        self.assertIn("--forge-deps", p.stdout)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `python3 -m unittest tools.tests.test_install -v`
Expected: 4 个 ERROR，报错为 `UnicodeDecodeError`，或 install.sh 输出 `TARGET\xef: unbound variable`；外加 1 个 FAIL（帮助里没有 `--render-deps`）。原因见下一步。

- [ ] **Step 3: 先修现有的 bash 3.2 问题**

macOS 自带的 bash 3.2 在 UTF-8 环境下，会把紧跟在变量名后面的中文全角字符，当成变量名的一部分。再加上脚本开了 `set -u`，就会报 `unbound variable` 并退出。

现有 install.sh 有 3 处这种写法，在用户终端里直接运行也会崩。全部改成 `${VAR}` 形式：

| 原写法 | 改为 |
|---|---|
| `skipped+=("$name（目标已存在且不是本脚本安装的，用 --force 覆盖）")` | `skipped+=("${name}（目标已存在且不是本脚本安装的，用 --force 覆盖）")` |
| `skipped+=("$s（zerox 该版本里没有这个 skill）")` | `skipped+=("${s}（zerox 该版本里没有这个 skill）")` |
| `echo "安装到：$TARGET（方式：$MODE）"` | `echo "安装到：${TARGET}（方式：${MODE}）"` |

**约定**：本计划以后新写的 shell 代码里，变量一律写成 `${VAR}`。

Run: `grep -nE '\$[A-Za-z_][A-Za-z0-9_]*[^ -~]' install.sh || echo 没有残留`
Expected: `没有残留`（这条命令查找"变量名后面紧跟非 ASCII 字符"的写法）。

- [ ] **Step 4: 修改 `install.sh`**

(a) 把文件开头的用法注释（第 2–15 行，也就是到 `#   CACHE_DIR …` 那一行为止）整体替换为下面这段。不要动第 16 行的 `set -euo pipefail`。新注释占第 2–21 行，所以帮助输出的 `sed` 行号改成 `2,21p`：

```bash
# 安装 Allen 的方法论 skill 系统、运行时（_allen-runtime），以及 zerox.lock 里固定版本的 zerox skill。
#
# 用法：
#   ./install.sh                     安装到 ~/.claude/skills（复制）
#   ./install.sh --target DIR        安装到其他目录
#   ./install.sh --link              用软链接代替复制（在本仓库里改 skill 立即生效）
#   ./install.sh --no-zerox          只装本仓库的 skill 和运行时
#   ./install.sh --render-deps       额外安装出成品所需的依赖：LibreOffice 等系统工具、Python 虚拟环境、
#                                    Playwright Chromium、报告引擎的 npm 依赖与字体，并生成能力探测任务
#   ./install.sh --forge-deps        已弃用，等同 --render-deps
#   ./install.sh --remove-old        删除旧版 skill（consulting-analysis 等三个旧名字）
#   ./install.sh --force             覆盖目标目录里不是本脚本装的同名 skill 或运行时
#
# 环境变量：
#   ZEROX_REPO   改用其他 zerox 仓库地址（例如自己的 fork）
#   CACHE_DIR    zerox 源码缓存位置，默认 ~/.cache/allen-skills
#   ALLEN_VENV   Python 虚拟环境位置，默认 ~/.cache/allen-skills/venv
#
# 运行时（_allen-runtime）：复制模式下是 vendor/ 和 tools/ 的副本；--link 模式下是指向本仓库的软链接。
# 复制模式重新安装会清掉运行时里的 npm 依赖和探测结果，之后需要重新运行 --render-deps。
```

(b) 变量区：在 `FORCE=0` 之后加：

```bash
RENDER_DEPS=0
RUNTIME_NAME="_allen-runtime"
VENV="${ALLEN_VENV:-${XDG_CACHE_HOME:-$HOME/.cache}/allen-skills/venv}"
```

(c) 参数解析：把原来的 `--forge-deps) FORGE_DEPS=1; shift ;;` 替换为：

```bash
    --render-deps) RENDER_DEPS=1; shift ;;
    --forge-deps) echo "提示：--forge-deps 已弃用，请改用 --render-deps。" >&2; RENDER_DEPS=1; FORGE_DEPS=1; shift ;;
```

并把 `-h|--help) sed -n '2,17p' "$0"; exit 0 ;;` 改为 `-h|--help) sed -n '2,21p' "$0"; exit 0 ;;`。

`VENV` 的默认值必须与 `tools/lib/runtime.py` 的 `venv_python()` 一致。在 `VENV=` 那一行上方加注释：`# 与 tools/lib/runtime.py 的 venv_python() 保持一致`。

(d) 在 `place()` 函数之后，加 `place_runtime()`：

```bash
# 安装运行时 TARGET/_allen-runtime
place_runtime() {
  local dest="${TARGET}/${RUNTIME_NAME}"
  if [ -e "${dest}" ] || [ -L "${dest}" ]; then
    if [ -L "${dest}" ] || [ -f "${dest}/${MARKER}" ] || [ "${FORCE}" = 1 ]; then
      rm -rf "${dest}"
    else
      skipped+=("${RUNTIME_NAME}（目标已存在且不是本脚本安装的，用 --force 覆盖）")
      return 0
    fi
  fi
  if [ "${MODE}" = "link" ]; then
    ln -s "${REPO_DIR}" "${dest}"
  else
    mkdir -p "${dest}"
    rsync -a --exclude node_modules --exclude .font-venv --exclude __pycache__ \
      --exclude .probe-task --exclude .probe.json "${REPO_DIR}/vendor" "${REPO_DIR}/tools" "${dest}/"
    echo "source=${REPO_DIR}" > "${dest}/${MARKER}"
  fi
  installed+=("${RUNTIME_NAME}")
}
```

(e) 在"# 1. 本仓库的 skill"那个 for 循环结束之后，加一行：

```bash
place_runtime
```

- [ ] **Step 5: 运行测试，确认通过**

Run: `python3 -m unittest tools.tests.test_install -v`
Expected: 5 个测试全部 `ok`。

- [ ] **Step 6: 在 UTF-8 终端里手动跑一次**

Run: `LC_ALL=en_US.UTF-8 bash install.sh --no-zerox --target /tmp/allen-install-check; echo "exit=$?"; rm -rf /tmp/allen-install-check`
Expected: 最后一行输出 `安装到：/tmp/allen-install-check（方式：copy）` 和已安装列表，`exit=0`。

- [ ] **Step 7: 提交**

```bash
git add install.sh tools/tests/test_install.py
git -c user.name="allenwy109" -c user.email="51287374+allenwy109@users.noreply.github.com" commit -m "feat(install): install _allen-runtime in copy and link modes

Also fix bash 3.2 unbound-variable errors when a variable is followed
by full-width characters.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: install.sh —— `--render-deps`

**Files:**
- Create: `tools/requirements-render.txt`
- Modify: `install.sh`

这一步会改动本机：用 Homebrew 安装 LibreOffice 等工具，下载 Chromium。单元测试不覆盖实际安装，实际运行放在 Task 10，执行前需要用户确认。

- [ ] **Step 1: 写 `tools/requirements-render.txt`**

```
# 出成品所需的 Python 包：thinkcell-charts（python-pptx、openpyxl）与 onepager（playwright）的需求并集
python-pptx>=1.0
openpyxl>=3.1
playwright>=1.40,<2.0
```

- [ ] **Step 2: 在 `install.sh` 的 `place_runtime()` 之后加 `render_deps()`**

```bash
# 安装出成品所需的依赖（设计 §9）
render_deps() {
  local rt="${TARGET}/${RUNTIME_NAME}"
  if [ ! -d "${rt}/vendor/report-forge" ]; then
    echo "错误：没有找到 ${rt}/vendor/report-forge，无法安装渲染依赖。" >&2
    return 1
  fi
  if ! command -v brew >/dev/null 2>&1; then
    echo "错误：需要 Homebrew（https://brew.sh）。" >&2
    return 1
  fi
  echo "[1/5] 系统工具（Homebrew）：poppler、tesseract、tesseract-lang、pandoc、LibreOffice ……"
  for f in poppler tesseract tesseract-lang pandoc; do
    brew list --formula "${f}" >/dev/null 2>&1 || brew install "${f}"
  done
  [ -d /Applications/LibreOffice.app ] || brew install --cask libreoffice

  echo "[2/5] Python 虚拟环境：${VENV} ……"
  local py=""
  for c in python3.13 python3.12 python3.11 python3.10 python3; do
    if command -v "${c}" >/dev/null 2>&1 && "${c}" -c 'import sys; sys.exit(0 if sys.version_info[:2] >= (3, 10) else 1)'; then
      py="${c}"; break
    fi
  done
  if [ -z "${py}" ]; then
    echo "错误：需要 Python 3.10 或更高版本。" >&2
    return 1
  fi
  [ -x "${VENV}/bin/python" ] || "${py}" -m venv "${VENV}"
  "${VENV}/bin/python" -m pip install -q --upgrade pip
  "${VENV}/bin/python" -m pip install -q -r "${rt}/tools/requirements-render.txt"

  echo "[3/5] Playwright Chromium（海报截图用）……"
  "${VENV}/bin/python" -m playwright install chromium

  echo "[4/5] 报告引擎的 npm 依赖与字体环境 ……"
  (cd "${rt}/vendor/report-forge" && npm ci && npm run setup-fonts)

  echo "[5/5] 报告引擎能力探测任务 ……"
  rm -rf "${rt}/.probe-task"
  (cd "${rt}/vendor/report-forge" && node scripts/probe_capabilities.cjs "${rt}/.probe-task")
  echo "下一步（必须由 Claude 在会话里完成看图）："
  echo "  1. 打开 ${rt}/.probe-task/vision-challenge.png，按引擎要求把看到的内容写成 response.json："
  echo '     {"code":"图中六字符","shape_left_to_right":["颜色 形状","颜色 形状","颜色 形状"]}'
  echo "  2. 运行 python3 ${rt}/tools/record_probe.py --response <response.json>"
  echo "  3. 运行 python3 ${rt}/tools/doctor.py 确认全部通过"
}
```

- [ ] **Step 3: 在 `install.sh` 里调用**

在"# 2. zerox skill"那一段之前，加：

```bash
if [ "${RENDER_DEPS}" = 1 ]; then
  render_deps
fi
```

原来 zerox 段里的 `if [ "$FORGE_DEPS" = 1 ] && [ -d "$TARGET/zerox-consulting-report-forge" ]` 那一块保持不变。在计划 8 之前，场景 skill 仍在调用 zerox，`--forge-deps` 仍要能给它装依赖。

- [ ] **Step 4: 给"没有 Homebrew"的情况加测试**

在 `tools/tests/test_install.py` 的 `InstallRuntimeTest` 类里加：

```python
    def test_render_deps_without_homebrew_fails_clearly(self):
        env = {"PATH": "/usr/bin:/bin", "HOME": self.tmp.name, "LC_ALL": "en_US.UTF-8"}
        p = subprocess.run(["bash", str(ROOT / "install.sh"), "--no-zerox", "--render-deps", "--target", str(self.target)],
                           capture_output=True, text=True, env=env)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("需要 Homebrew", p.stderr)
```

PATH 只留 `/usr/bin:/bin`，Homebrew（`/opt/homebrew/bin`）就不在里面；CI 的 Ubuntu 本来就没有 brew。`rsync` 在这两处都在 `/usr/bin` 下。

- [ ] **Step 5: 语法检查与测试**

Run:
```bash
bash -n install.sh && echo 语法正确
grep -nE '\$[A-Za-z_][A-Za-z0-9_]*[^ -~]' install.sh || echo 没有残留
python3 -m unittest tools.tests.test_install -v
```
Expected: 输出 `语法正确`、`没有残留`；6 个测试全部 `ok`。

- [ ] **Step 6: 提交**

```bash
git add install.sh tools/requirements-render.txt tools/tests/test_install.py
git -c user.name="allenwy109" -c user.email="51287374+allenwy109@users.noreply.github.com" commit -m "feat(install): add --render-deps for engine dependencies

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: doctor.py

**Files:**
- Create: `tools/doctor.py`
- Test: `tools/tests/test_doctor.py`

- [ ] **Step 1: 写失败的测试**

`tools/tests/test_doctor.py`：

```python
import json
import pathlib
import unittest

from tools import doctor

RT = pathlib.Path("/rt")
FORGE = RT / "vendor" / "report-forge"
VENV_PY = "/venv/bin/python"
CHROMIUM = "/pw/chromium-1208/chrome"


class FakeEnv:
    """按"命令行包含的子串"返回预设结果的假环境。"""

    def __init__(self):
        self.commands = {"node", "pdfinfo", "pdftotext", "pdftoppm", "pdffonts", "tesseract", "pandoc"}
        self.paths = {VENV_PY, CHROMIUM, doctor.CHROME, doctor.SOFFICE_APP,
                      str(FORGE / "node_modules/playwright"), str(FORGE / ".font-venv/bin/python"),
                      str(RT / ".probe.json"), str(RT / "vendor" / "vendor.lock")}
        self.files = {
            str(RT / ".probe.json"): json.dumps({"verified": True, "commit": "abc"}),
            str(RT / "vendor" / "vendor.lock"): json.dumps({"commit": "abc"}),
        }
        self.rules = [
            ("node --version", (0, "v22.23.1\n")),
            ("import sys, pptx, openpyxl, playwright", (0, "3.11\n")),
            ("executable_path", (0, CHROMIUM + "\n")),
            ("--dump-dom", (0, "<html></html>")),
            ("tesseract --list-langs", (0, "List of available languages (3):\nchi_sim\neng\nosd\n")),
            ("require('playwright')", (0, "")),
        ]
        self.free = 36.0
        self.vendor = []
        self.convert = (True, "转换成功")

    def soffice_convert(self, soffice):
        return self.convert

    def which(self, cmd):
        return f"/usr/bin/{cmd}" if cmd in self.commands else None

    def run(self, args, timeout=60, env=None):
        line = " ".join(str(a) for a in args)
        for needle, res in self.rules:
            if needle in line:
                return res
        return 127, "not found"

    def exists(self, path):
        return str(path) in self.paths

    def read(self, path):
        return self.files[str(path)]

    def free_gb(self, path):
        return self.free

    def vendor_errors(self, rt):
        return self.vendor

    def venv_python(self):
        return VENV_PY


def by_name(results):
    return {r["name"]: r for r in results}


class DoctorTest(unittest.TestCase):
    def test_all_good(self):
        results = doctor.run_all(FakeEnv(), RT)
        bad = [r for r in results if r["status"] != doctor.PASS]
        self.assertEqual(bad, [])
        self.assertEqual(doctor.exit_code(results), 0)

    def test_old_node(self):
        e = FakeEnv()
        e.rules.insert(0, ("node --version", (0, "v18.19.0\n")))
        r = by_name(doctor.run_all(e, RT))["Node.js ≥20"]
        self.assertEqual(r["status"], doctor.OLD)
        self.assertEqual(doctor.exit_code(doctor.run_all(e, RT)), 1)

    def test_tesseract_without_chinese(self):
        e = FakeEnv()
        e.rules.insert(0, ("tesseract --list-langs", (0, "List of available languages (1):\neng\n")))
        r = by_name(doctor.run_all(e, RT))["Tesseract（含 chi_sim）"]
        self.assertEqual(r["status"], doctor.MISSING)
        self.assertIn("tesseract-lang", r["fix"])

    def test_missing_chromium_executable(self):
        e = FakeEnv()
        e.paths.discard(CHROMIUM)
        r = by_name(doctor.run_all(e, RT))["Playwright Chromium（海报截图）"]
        self.assertEqual(r["status"], doctor.MISSING)
        self.assertIn("playwright install chromium", r["fix"])

    def test_stale_probe(self):
        e = FakeEnv()
        e.files[str(RT / ".probe.json")] = json.dumps({"verified": True, "commit": "old"})
        r = by_name(doctor.run_all(e, RT))["报告引擎能力探测（看图验证）"]
        self.assertEqual(r["status"], doctor.MISSING)

    def test_low_disk_is_warning_only(self):
        e = FakeEnv()
        e.free = 2.0
        results = doctor.run_all(e, RT)
        self.assertEqual(by_name(results)["磁盘剩余空间"]["status"], doctor.WARN)
        self.assertEqual(doctor.exit_code(results), 0)

    def test_vendor_errors(self):
        e = FakeEnv()
        e.vendor = ["文件被改动：onepager/x"]
        r = by_name(doctor.run_all(e, RT))["vendor 引擎完整性"]
        self.assertEqual(r["status"], doctor.MISSING)
        self.assertIn("文件被改动", r["detail"])

    def test_every_check_reports_its_failure(self):
        """每一项检查都至少有一个失败用例，并且给出修复办法。"""
        venv = "Python 虚拟环境（python-pptx、openpyxl、playwright）"
        probe = "报告引擎能力探测（看图验证）"
        cases = [
            ("node 不存在", lambda e: e.commands.discard("node"), "Node.js ≥20", doctor.MISSING),
            ("虚拟环境不存在", lambda e: e.paths.discard(VENV_PY), venv, doctor.MISSING),
            ("虚拟环境缺包", lambda e: e.rules.insert(0, ("import sys, pptx", (1, "ModuleNotFoundError: pptx"))), venv, doctor.MISSING),
            ("虚拟环境 Python 太旧", lambda e: e.rules.insert(0, ("import sys, pptx", (0, "3.9\n"))), venv, doctor.OLD),
            ("Chrome 启动失败", lambda e: e.rules.insert(0, ("--dump-dom", (1, "crash"))), "Google Chrome 无头启动（报告引擎）", doctor.MISSING),
            ("Chrome 不存在", lambda e: e.paths.discard(doctor.CHROME), "Google Chrome 无头启动（报告引擎）", doctor.MISSING),
            ("缺 pdffonts", lambda e: e.commands.discard("pdffonts"), "Poppler（pdfinfo、pdftotext、pdftoppm、pdffonts）", doctor.MISSING),
            ("缺 tesseract", lambda e: e.commands.discard("tesseract"), "Tesseract（含 chi_sim）", doctor.MISSING),
            ("缺 pandoc", lambda e: e.commands.discard("pandoc"), "Pandoc", doctor.MISSING),
            ("缺 LibreOffice", lambda e: e.paths.discard(doctor.SOFFICE_APP), "LibreOffice（能实际转换文件）", doctor.MISSING),
            ("LibreOffice 转换失败", lambda e: setattr(e, "convert", (False, "source file could not be loaded")), "LibreOffice（能实际转换文件）", doctor.MISSING),
            ("缺 npm 依赖", lambda e: e.paths.discard(str(FORGE / "node_modules/playwright")), "报告引擎 npm 依赖与字体环境", doctor.MISSING),
            ("缺探测记录", lambda e: e.paths.discard(str(RT / ".probe.json")), probe, doctor.MISSING),
            ("探测未通过", lambda e: e.files.__setitem__(str(RT / ".probe.json"), json.dumps({"verified": False, "commit": "abc"})), probe, doctor.MISSING),
            ("探测记录损坏", lambda e: e.files.__setitem__(str(RT / ".probe.json"), "{"), probe, doctor.MISSING),
            ("NODE_PATH 下没有 playwright", lambda e: e.rules.insert(0, ("require('playwright')", (1, "Cannot find module"))), "thinkcell 浏览器测试前提（NODE_PATH 与 TC_BROWSER_PATH）", doctor.MISSING),
        ]
        for label, mutate, name, status in cases:
            with self.subTest(label):
                e = FakeEnv()
                mutate(e)
                r = by_name(doctor.run_all(e, RT))[name]
                self.assertEqual(r["status"], status)
                self.assertTrue(r["fix"])

    def test_real_soffice_convert_with_missing_binary(self):
        ok, detail = doctor.Env().soffice_convert("/nonexistent/soffice")
        self.assertFalse(ok)
        self.assertTrue(detail)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `python3 -m unittest tools.tests.test_doctor -v`
Expected: `ImportError: cannot import name 'doctor'`

- [ ] **Step 3: 写 `tools/doctor.py`**

```python
#!/usr/bin/env python3
"""检查出成品所需的本机环境（设计 §9）。

用法：python3 tools/doctor.py [--json]
每项给出：通过 / 缺失 / 版本不足 / 警告，以及修复办法。
有任何一项是"缺失"或"版本不足"时，以状态 1 退出；"警告"不影响退出状态。
"""
import argparse
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from tools import vendor_sync  # noqa: E402
from tools.lib import runtime  # noqa: E402

CHROME = runtime.CHROME
SOFFICE_APP = runtime.SOFFICE_APP
MIN_FREE_GB = 5
PASS, MISSING, OLD, WARN = "通过", "缺失", "版本不足", "警告"
RENDER_FIX = "./install.sh --render-deps"


class Env:
    """真实环境；测试时用假对象代替。"""

    def which(self, cmd):
        return shutil.which(cmd)

    def run(self, args, timeout=60, env=None):
        try:
            p = subprocess.run(args, capture_output=True, text=True, timeout=timeout, env=env)
            return p.returncode, (p.stdout or "") + (p.stderr or "")
        except (OSError, subprocess.TimeoutExpired) as e:
            return 127, str(e)

    def exists(self, path):
        return pathlib.Path(path).exists()

    def read(self, path):
        return pathlib.Path(path).read_text(encoding="utf-8")

    def free_gb(self, path):
        return shutil.disk_usage(path).free / 1e9

    def vendor_errors(self, rt):
        return vendor_sync.check(pathlib.Path(rt) / "vendor")

    def venv_python(self):
        return str(runtime.venv_python())

    def soffice_convert(self, soffice):
        """实际用 LibreOffice 把一个文本文件转成 PDF，返回 (是否成功, 说明)。"""
        with tempfile.TemporaryDirectory() as tmp:
            src = pathlib.Path(tmp) / "t.txt"
            src.write_text("doctor\n", encoding="utf-8")
            # 用独立的临时配置目录，避免和用户正开着的 LibreOffice 抢配置
            profile = "-env:UserInstallation=" + (pathlib.Path(tmp) / "profile").as_uri()
            code, out = self.run([soffice, profile, "--headless", "--convert-to", "pdf", "--outdir", tmp, str(src)], timeout=180)
            ok = code == 0 and (pathlib.Path(tmp) / "t.pdf").is_file()
            return ok, "转换成功" if ok else out.strip()[-200:]


def version(text):
    m = re.search(r"(\d+)\.(\d+)", text or "")
    return (int(m.group(1)), int(m.group(2))) if m else None


def result(name, status, detail, fix=""):
    return {"name": name, "status": status, "detail": detail, "fix": fix}


def check_node(e, rt):
    name = "Node.js ≥20"
    if not e.which("node"):
        return result(name, MISSING, "找不到 node", "安装 Node.js 20 或更高版本（例如 fnm install 22）")
    _, out = e.run(["node", "--version"])
    v = version(out)
    if not v or v < (20, 0):
        return result(name, OLD, out.strip(), "升级到 Node.js 20 或更高版本")
    return result(name, PASS, out.strip())


def check_venv(e, rt):
    name = "Python 虚拟环境（python-pptx、openpyxl、playwright）"
    py = e.venv_python()
    if not e.exists(py):
        return result(name, MISSING, f"{py} 不存在", RENDER_FIX)
    code, out = e.run([py, "-c", "import sys, pptx, openpyxl, playwright; print('%d.%d' % sys.version_info[:2])"])
    if code != 0:
        return result(name, MISSING, out.strip()[-200:], RENDER_FIX)
    v = version(out)
    if not v or v < (3, 10):
        return result(name, OLD, out.strip(), f"删除 {pathlib.Path(py).parent.parent} 后重新运行 {RENDER_FIX}")
    return result(name, PASS, f"Python {out.strip()}")


def check_playwright_chromium(e, rt):
    name = "Playwright Chromium（海报截图）"
    py = e.venv_python()
    if not e.exists(py):
        return result(name, MISSING, "虚拟环境不存在", RENDER_FIX)
    code, out = e.run([py, "-c", "from playwright.sync_api import sync_playwright\nwith sync_playwright() as p: print(p.chromium.executable_path)"])
    path = out.strip().splitlines()[-1] if out.strip() else ""
    if code != 0 or not path or not e.exists(path):
        return result(name, MISSING, path or out.strip()[-200:], f"{py} -m playwright install chromium")
    return result(name, PASS, path)


def check_chrome(e, rt):
    name = "Google Chrome 无头启动（报告引擎）"
    if not e.exists(CHROME):
        return result(name, MISSING, CHROME, "安装 Google Chrome")
    code, out = e.run([CHROME, "--headless=new", "--disable-gpu", "--dump-dom", "about:blank"], timeout=60)
    if code != 0:
        return result(name, MISSING, out.strip()[-200:], "确认 Google Chrome 能正常启动")
    return result(name, PASS, CHROME)


def check_poppler(e, rt):
    name = "Poppler（pdfinfo、pdftotext、pdftoppm、pdffonts）"
    missing = [c for c in ("pdfinfo", "pdftotext", "pdftoppm", "pdffonts") if not e.which(c)]
    if missing:
        return result(name, MISSING, "缺 " + "、".join(missing), "brew install poppler")
    return result(name, PASS, "四个命令都在")


def check_tesseract(e, rt):
    name = "Tesseract（含 chi_sim）"
    if not e.which("tesseract"):
        return result(name, MISSING, "找不到 tesseract", "brew install tesseract tesseract-lang")
    _, out = e.run(["tesseract", "--list-langs"])
    if "chi_sim" not in out.split():
        return result(name, MISSING, "缺少中文简体语言包 chi_sim", "brew install tesseract-lang")
    return result(name, PASS, "chi_sim 可用")


def check_pandoc(e, rt):
    name = "Pandoc"
    if not e.which("pandoc"):
        return result(name, MISSING, "找不到 pandoc", "brew install pandoc")
    return result(name, PASS, "可用")


def check_soffice(e, rt):
    name = "LibreOffice（能实际转换文件）"
    path = SOFFICE_APP if e.exists(SOFFICE_APP) else e.which("soffice")
    if not path:
        return result(name, MISSING, "找不到 soffice", "brew install --cask libreoffice")
    ok, detail = e.soffice_convert(path)
    if not ok:
        return result(name, MISSING, detail, "重新安装 LibreOffice，并确认能在终端里运行 soffice --headless")
    return result(name, PASS, f"{path}：{detail}")


def check_forge_deps(e, rt):
    name = "报告引擎 npm 依赖与字体环境"
    forge = runtime.engine_path(rt, "report-forge")
    missing = [x for x in ("node_modules/playwright", ".font-venv/bin/python") if not e.exists(str(forge / x))]
    if missing:
        return result(name, MISSING, "缺 " + "、".join(missing), f"cd {forge} && npm ci && npm run setup-fonts")
    return result(name, PASS, str(forge))


def check_probe(e, rt):
    name = "报告引擎能力探测（看图验证）"
    fix = f"{RENDER_FIX}，然后在 Claude 会话里完成看图验证（tools/record_probe.py）"
    probe = pathlib.Path(rt) / ".probe.json"
    if not e.exists(str(probe)):
        return result(name, MISSING, "还没有验证记录", fix)
    try:
        data = json.loads(e.read(str(probe)))
        lock = json.loads(e.read(str(pathlib.Path(rt) / "vendor" / "vendor.lock")))
    except (OSError, ValueError) as err:
        return result(name, MISSING, f"验证记录或 vendor.lock 无法读取：{err}", fix)
    if not data.get("verified"):
        return result(name, MISSING, "上次验证没有通过", fix)
    if data.get("commit") != lock.get("commit"):
        return result(name, MISSING, "验证记录对应的引擎版本已过期", fix)
    return result(name, PASS, f"已验证（{data.get('at', '')}）")


def check_node_playwright(e, rt):
    name = "thinkcell 浏览器测试前提（NODE_PATH 与 TC_BROWSER_PATH）"
    node_modules = runtime.engine_path(rt, "report-forge") / "node_modules"
    code, out = e.run(["node", "-e", "require('playwright')"], env=dict(os.environ, NODE_PATH=str(node_modules)))
    if code != 0:
        return result(name, MISSING, "NODE_PATH 下加载不到 playwright", f"cd {node_modules.parent} && npm ci")
    if not e.exists(CHROME):
        return result(name, MISSING, "TC_BROWSER_PATH 要指向 Google Chrome，但它不存在", "安装 Google Chrome")
    return result(name, PASS, f"NODE_PATH={node_modules}；TC_BROWSER_PATH={CHROME}")


def check_disk(e, rt):
    name = "磁盘剩余空间"
    gb = e.free_gb(str(rt))
    if gb < MIN_FREE_GB:
        return result(name, WARN, f"剩余 {gb:.1f} GB，低于 {MIN_FREE_GB} GB", "清理磁盘空间")
    return result(name, PASS, f"剩余 {gb:.1f} GB")


def check_vendor(e, rt):
    name = "vendor 引擎完整性"
    errors = e.vendor_errors(rt)
    if errors:
        return result(name, MISSING, "；".join(errors[:5]) + ("……" if len(errors) > 5 else ""), "python3 tools/vendor_sync.py sync")
    return result(name, PASS, "与 vendor.lock 一致")


CHECKS = [check_vendor, check_node, check_venv, check_playwright_chromium, check_chrome, check_poppler,
          check_tesseract, check_pandoc, check_soffice, check_forge_deps, check_probe, check_node_playwright, check_disk]


def run_all(e, rt):
    return [c(e, rt) for c in CHECKS]


def exit_code(results):
    return 1 if any(r["status"] in (MISSING, OLD) for r in results) else 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="检查出成品所需的本机环境")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    try:
        rt = runtime.runtime_root()
    except runtime.RuntimeNotFound as err:
        print(f"[{MISSING}] 运行时：{err}")
        return 1
    results = run_all(Env(), rt)
    if a.json:
        print(json.dumps({"runtime": str(rt), "results": results}, ensure_ascii=False, indent=1))
    else:
        print(f"运行时：{rt}")
        for r in results:
            line = f"[{r['status']}] {r['name']}：{r['detail']}"
            if r["status"] != PASS and r["fix"]:
                line += f"\n        修复：{r['fix']}"
            print(line)
    return exit_code(results)


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: 运行测试，确认通过**

Run: `python3 -m unittest tools.tests.test_doctor -v`
Expected: 9 个测试全部 `ok`（其中一个含 16 个子用例）。

- [ ] **Step 5: 在本机实际运行一次（只读，不安装任何东西）**

Run: `python3 tools/doctor.py; echo "exit=$?"`
Expected：
- vendor、Node、Chrome、Poppler、Tesseract、Pandoc 为"通过"；
- 虚拟环境、Playwright Chromium、LibreOffice、npm 依赖、能力探测、thinkcell 前提为"缺失"，并给出修复办法（本机已有 Poppler，pdffonts 应为通过）；
- `exit=1`。

这些缺失项正是 Task 10 要装的。

- [ ] **Step 6: 提交**

```bash
git add tools/doctor.py tools/tests/test_doctor.py
git -c user.name="allenwy109" -c user.email="51287374+allenwy109@users.noreply.github.com" commit -m "feat(doctor): add environment checks for rendering engines

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: record_probe.py

**Files:**
- Create: `tools/record_probe.py`
- Test: `tools/tests/test_record_probe.py`

- [ ] **Step 1: 写失败的测试**

`tools/tests/test_record_probe.py`：

```python
import json
import pathlib
import tempfile
import unittest
from types import SimpleNamespace

from tools import record_probe


class RecordProbeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.rt = pathlib.Path(self.tmp.name)
        (self.rt / "vendor" / "report-forge").mkdir(parents=True)
        (self.rt / "vendor" / "vendor.lock").write_text(json.dumps({"commit": "abc123"}), encoding="utf-8")
        self.response = self.rt / "response.json"
        self.response.write_text("{}", encoding="utf-8")
        self.calls = []

    def tearDown(self):
        self.tmp.cleanup()

    def runner(self, code):
        def run(args, cwd=None, capture_output=None, text=None):
            self.calls.append((args, cwd))
            return SimpleNamespace(returncode=code, stdout="verify output", stderr="")
        return run

    def test_success_writes_verified_record(self):
        code = record_probe.run(self.rt, self.response, runner=self.runner(0), now="2026-10-22T10:00:00+00:00")
        self.assertEqual(code, 0)
        data = json.loads((self.rt / ".probe.json").read_text(encoding="utf-8"))
        self.assertEqual(data["verified"], True)
        self.assertEqual(data["commit"], "abc123")
        self.assertEqual(data["at"], "2026-10-22T10:00:00+00:00")
        args, cwd = self.calls[0]
        self.assertEqual(args[:2], ["node", "scripts/probe_capabilities.cjs"])
        self.assertEqual(args[2:], [str(self.rt / ".probe-task"), "--verify", str(self.response)])
        self.assertEqual(cwd, self.rt / "vendor" / "report-forge")

    def test_failure_writes_unverified_record(self):
        code = record_probe.run(self.rt, self.response, runner=self.runner(1))
        self.assertEqual(code, 1)
        data = json.loads((self.rt / ".probe.json").read_text(encoding="utf-8"))
        self.assertEqual(data["verified"], False)

    def test_missing_response_file(self):
        code = record_probe.run(self.rt, self.rt / "nope.json", runner=self.runner(0))
        self.assertEqual(code, 2)
        self.assertFalse((self.rt / ".probe.json").exists())

    def test_node_not_found(self):
        def run(*args, **kwargs):
            raise FileNotFoundError("node")
        code = record_probe.run(self.rt, self.response, runner=run)
        self.assertEqual(code, 2)
        self.assertFalse((self.rt / ".probe.json").exists())


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `python3 -m unittest tools.tests.test_record_probe -v`
Expected: `ImportError: cannot import name 'record_probe'`

- [ ] **Step 3: 写 `tools/record_probe.py`**

```python
#!/usr/bin/env python3
"""完成报告引擎的能力探测验证，并记录结果（设计 §9）。

前提：已运行 ./install.sh --render-deps，生成了 <运行时>/.probe-task/。
做法：由 Claude 在会话里实际打开 <运行时>/.probe-task/vision-challenge.png，按引擎要求写 response.json：
  {"code":"图中六字符","shape_left_to_right":["颜色 形状","颜色 形状","颜色 形状"]}
不能读取答案文件代替看图。然后运行：
  python3 tools/record_probe.py --response <response.json>
结果写入 <运行时>/.probe.json，doctor 据此判断是否已验证。退出码：0 通过；1 未通过；2 参数错误。
"""
import argparse
import json
import pathlib
import subprocess
import sys
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from tools.lib import runtime  # noqa: E402


def run(rt, response, runner=subprocess.run, now=None):
    rt, response = pathlib.Path(rt), pathlib.Path(response)
    if not response.is_file():
        print(f"错误：找不到 {response}", file=sys.stderr)
        return 2
    forge = runtime.engine_path(rt, "report-forge")
    try:
        p = runner(["node", "scripts/probe_capabilities.cjs", str(rt / ".probe-task"), "--verify", str(response)],
                   cwd=forge, capture_output=True, text=True)
    except OSError as err:
        print(f"错误：无法运行 node：{err}", file=sys.stderr)
        return 2
    output = (p.stdout or "") + (p.stderr or "")
    lock = json.loads((rt / "vendor" / "vendor.lock").read_text(encoding="utf-8"))
    record = {
        "verified": p.returncode == 0,
        "commit": lock.get("commit"),
        "at": now or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "output_tail": output[-500:],
    }
    (rt / ".probe.json").write_text(json.dumps(record, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(output.strip())
    print("能力探测验证通过" if record["verified"] else "能力探测验证没有通过")
    return 0 if record["verified"] else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description="完成报告引擎能力探测的看图验证并记录结果")
    ap.add_argument("--response", required=True, help="看图后写好的 response.json")
    a = ap.parse_args(argv)
    try:
        rt = runtime.runtime_root()
    except runtime.RuntimeNotFound as err:
        print(f"错误：{err}", file=sys.stderr)
        return 2
    return run(rt, a.response)


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: 运行测试，确认通过**

Run: `python3 -m unittest tools.tests.test_record_probe -v`
Expected: 4 个测试全部 `ok`。

- [ ] **Step 5: 提交**

```bash
git add tools/record_probe.py tools/tests/test_record_probe.py
git -c user.name="allenwy109" -c user.email="51287374+allenwy109@users.noreply.github.com" commit -m "feat(probe): record report engine capability verification

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: validate.py、selftest.sh、CI

**Files:**
- Modify: `tools/validate.py`
- Create: `tools/selftest.sh`
- Modify: `.github/workflows/validate.yml`

- [ ] **Step 1: 先确认 validate.py 现在还不检查 vendor**

Run:
```bash
cp vendor/onepager/LICENSE.txt /tmp/onepager-license.bak
echo tamper >> vendor/onepager/LICENSE.txt
python3 tools/validate.py; echo "exit=$?"
cp /tmp/onepager-license.bak vendor/onepager/LICENSE.txt
```
Expected: `exit=0`。这说明 validate.py 还发现不了被篡改的 vendor 文件，下一步要补上。

- [ ] **Step 2: 修改 `tools/validate.py`**

(a) 在文件开头 docstring 的检查项列表末尾加一行：

```
5. vendor/ 下的引擎与 vendor.lock 一致，且没有残留的 SKILL.md。
```

(b) 在 `for w in warnings:` 这一行之前插入：

```python
vendor_dir = ROOT / "vendor"
if vendor_dir.is_dir():
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from tools import vendor_sync

    for e in vendor_sync.check(vendor_dir):
        errors.append("vendor：" + e)
```

- [ ] **Step 3: 验证篡改能被发现，复原后通过**

Run:
```bash
echo tamper >> vendor/onepager/LICENSE.txt
python3 tools/validate.py; echo "exit=$?"
cp /tmp/onepager-license.bak vendor/onepager/LICENSE.txt
python3 tools/validate.py; echo "exit=$?"
```
Expected：
- 第一次输出 `错误：vendor：文件被改动：onepager/LICENSE.txt` 和 `exit=1`；
- 第二次 `exit=0`，原有的 3 条提示照旧。

- [ ] **Step 4: 把上面的手工验证写成自动测试**

`tools/tests/test_validate.py`：

```python
import pathlib
import shutil
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]


def copy_repo(dst):
    shutil.copytree(ROOT, dst, ignore=shutil.ignore_patterns(".git", "node_modules", ".font-venv", "__pycache__", ".probe-task"))


class ValidateTest(unittest.TestCase):
    def run_validate(self, root):
        return subprocess.run(["python3", str(root / "tools" / "validate.py")], capture_output=True, text=True)

    def test_repo_passes(self):
        p = self.run_validate(ROOT)
        self.assertEqual(p.returncode, 0, p.stdout)

    def test_tampered_vendor_file_fails(self):
        with tempfile.TemporaryDirectory() as t:
            copy = pathlib.Path(t) / "repo"
            copy_repo(copy)
            with open(copy / "vendor" / "onepager" / "LICENSE.txt", "a", encoding="utf-8") as f:
                f.write("tamper\n")
            p = self.run_validate(copy)
            self.assertEqual(p.returncode, 1)
            self.assertIn("vendor：文件被改动：onepager/LICENSE.txt", p.stdout)

    def test_missing_lock_fails(self):
        with tempfile.TemporaryDirectory() as t:
            copy = pathlib.Path(t) / "repo"
            copy_repo(copy)
            (copy / "vendor" / "vendor.lock").unlink()
            p = self.run_validate(copy)
            self.assertEqual(p.returncode, 1)
            self.assertIn("vendor：缺少", p.stdout)


if __name__ == "__main__":
    unittest.main()
```

Run: `python3 -m unittest tools.tests.test_validate -v`
Expected: 3 个测试全部 `ok`。

- [ ] **Step 5: 写 `tools/selftest.sh`**

```bash
#!/usr/bin/env bash
# 自检（设计 §11）：单元测试、仓库结构、三个引擎自带的测试。
# 用法：tools/selftest.sh [--quick]
#   --quick  只跑单元测试和结构检查（不需要渲染依赖）
# 引擎测试在临时副本里运行，不会在 vendor/ 下留下产物；需要先完成 ./install.sh --render-deps。
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "== 单元测试"
python3 -m unittest discover -s tools/tests -t .
echo "== 仓库结构"
python3 tools/validate.py
if [ "${1:-}" = "--quick" ]; then
  echo "已跳过引擎测试（--quick）"
  exit 0
fi

echo "== 环境检查"
if ! python3 tools/doctor.py; then
  echo "错误：doctor 没有全部通过，先按上面的修复办法处理" >&2
  exit 1
fi

pyget() { python3 -c "import sys; sys.path.insert(0, '.'); from tools.lib import runtime; print(${1})"; }
RT="$(pyget 'runtime.runtime_root()')"
VENV_PY="$(pyget 'runtime.venv_python()')"
CHROME="$(pyget 'runtime.CHROME')"
export PATH="/Applications/LibreOffice.app/Contents/MacOS:${PATH}"
WORK="$(mktemp -d)"
trap 'rm -rf "${WORK}"' EXIT
copy_engine() { rsync -a --exclude node_modules --exclude .font-venv "${RT}/vendor/${1}/" "${WORK}/${1}/"; }

# 跑 Python unittest；有任何测试被跳过都算失败（依赖缺失时测试会自动跳过，不能当作通过）
run_py_tests() {
  (cd "${WORK}/${1}" && "${VENV_PY}" -m unittest discover -s tests -p 'test_*.py') 2>&1 | tee "${WORK}/unittest.log"
  if grep -q "skipped=" "${WORK}/unittest.log"; then
    echo "错误：${1} 有测试被跳过，说明有依赖不可用" >&2
    exit 1
  fi
}

echo "== report-forge"
copy_engine report-forge
ln -s "${RT}/vendor/report-forge/node_modules" "${WORK}/report-forge/node_modules"
ln -s "${RT}/vendor/report-forge/.font-venv" "${WORK}/report-forge/.font-venv"
(cd "${WORK}/report-forge" && npm test && npm run test:render && npm run test:upgrade-render)

echo "== thinkcell-charts"
copy_engine thinkcell-charts
(cd "${WORK}/thinkcell-charts" && "${VENV_PY}" tests/run_tests.py)
run_py_tests thinkcell-charts
(cd "${WORK}/thinkcell-charts" && NODE_PATH="${RT}/vendor/report-forge/node_modules" TC_BROWSER_PATH="${CHROME}" TC_PYTHON="${VENV_PY}" node tests/check_html_browser.cjs)

echo "== onepager"
copy_engine onepager
run_py_tests onepager

echo "自检全部通过"
```

Run: `chmod +x tools/selftest.sh && tools/selftest.sh --quick`
Expected：
- 单元测试全部 `OK`（45 个：vendor_sync 13、runtime 10、install 6、doctor 9、record_probe 4、validate 3）；
- validate 输出 `错误 0 个`；
- 最后一行 `已跳过引擎测试（--quick）`。

- [ ] **Step 6: 修改 `.github/workflows/validate.yml`**

在"检查 skill 结构"这一步之前，加一步：

```yaml
      - name: 单元测试
        run: python3 -m unittest discover -s tools/tests -t .
```

其余步骤不变。

- [ ] **Step 7: 提交**

```bash
git add tools/validate.py tools/selftest.sh tools/tests/test_validate.py .github/workflows/validate.yml
git -c user.name="allenwy109" -c user.email="51287374+allenwy109@users.noreply.github.com" commit -m "feat(selftest): check vendor integrity and add selftest script

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 10: 本机安装与实测（会改动本机，执行前先问用户）

这一步会：
- 用 Homebrew 安装 LibreOffice（约 1 GB）；
- 下载 Playwright Chromium（约 150 MB）；
- 在 `~/.cache/allen-skills/venv` 建虚拟环境；
- 在仓库的 `vendor/report-forge` 下安装 npm 依赖和字体环境（已被 .gitignore 忽略）。

**执行前先向用户确认**。安装目标用临时目录，不碰 `~/.claude/skills`。

- [ ] **Step 1: 安装到临时目标（软链接模式，运行时就是本仓库）**

Run:
```bash
./install.sh --link --no-zerox --render-deps --target "$HOME/.cache/allen-skills/stage-skills"
```
Expected：
- 依次输出 `[1/5]`…`[5/5]`；
- 最后打印看图验证的三步提示；
- 退出码 0。

- [ ] **Step 2: 看图验证（由 Claude 执行）**

1. 用 Read 工具打开 `.probe-task/vision-challenge.png`（在仓库根目录下），实际看图；
2. 把看到的六个字符和三个"颜色 形状"写进 `/tmp/probe-response.json`，格式：`{"code":"……","shape_left_to_right":["……","……","……"]}`；
3. 运行 `python3 tools/record_probe.py --response /tmp/probe-response.json`。

Expected: 最后一行输出 `能力探测验证通过`，退出码 0。没通过就重新仔细看图再试，不得读取答案文件。

- [ ] **Step 3: doctor 全部通过**

Run: `python3 tools/doctor.py; echo "exit=$?"`
Expected: 13 项都是"通过"（磁盘一项可以是"警告"），`exit=0`。

- [ ] **Step 4: 完整自检**

Run: `tools/selftest.sh`
Expected：
- 单元测试和结构检查通过；
- 环境检查（doctor）通过；
- report-forge 的 `npm test`、`test:render`、`test:upgrade-render` 通过；
- thinkcell 的三组测试通过；
- onepager 测试通过，且没有任何测试被跳过（`skipped=` 不出现；有跳过时脚本会直接报错退出）；
- 最后一行 `自检全部通过`。

任何一个引擎测试失败，都先用 `superpowers:systematic-debugging` 查清原因。不准修改 vendor 下的文件来让测试通过；如果确实要改引擎，按设计 §6.1 写补丁文件，并在补丁里写明原因。

- [ ] **Step 5: 确认仓库没有被弄脏**

Run: `git status --short && python3 tools/vendor_sync.py check`
Expected：
- `git status` 没有输出（node_modules、.font-venv、.probe-task、.probe.json 都已被忽略）；
- `vendor 检查通过`。

---

### Task 11: 计划 1 整体审查

- [ ] **Step 1: 派一个没参与开发的子代理审查**

给审查员的材料：
- 设计 §6.1、§8.2、§9、§11；
- 本计划；
- `git diff b434564..HEAD`；
- Task 10 各步的实际输出。

审查两项：
1. **符合性**：是否满足计划 1 的完成标志（doctor 全部通过、三个引擎自带测试通过、能力探测通过）。
2. **代码质量**：按设计 §8.2 的 5 条硬标准逐条检查。

问题分为阻塞、重要、轻微三级。

- [ ] **Step 2: 修复阻塞和重要问题，重新运行 `tools/selftest.sh`，并把审查结果写进 `docs/plans/2026-10-22-plan-1-review.md`**

- [ ] **Step 3: 更新路线图中计划 1 的状态为"已完成"，并提交**

```bash
git add docs/plans
git -c user.name="allenwy109" -c user.email="51287374+allenwy109@users.noreply.github.com" commit -m "docs(plans): complete plan 1 runtime

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
