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
