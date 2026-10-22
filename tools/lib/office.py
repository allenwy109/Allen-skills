"""调用 LibreOffice 做格式转换（设计 §4、§9）。

macOS 上无头运行的 LibreOffice 看不到系统字体，只能用它自带的字体，中文会整段丢失（文字层还在，但渲染不出来）。
解决办法：每次转换都用一个临时配置目录，在 user/fonts 下软链接一款系统中文字体。
这样不改动用户自己的 LibreOffice 设置，并发转换也不会争用同一个配置目录。
"""
import pathlib
import shutil
import subprocess
import tempfile

from tools.lib import runtime

# 按顺序找第一款存在的中文字体；值是它在 PDF 里的字体名前缀，用于检查是否真的用上了
CJK_FONTS = {
    "/System/Library/Fonts/Hiragino Sans GB.ttc": "HiraginoSansGB",
    "/System/Library/Fonts/STHeiti Medium.ttc": "STHeiti",
    "/System/Library/Fonts/STHeiti Light.ttc": "STHeiti",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc": "NotoSansCJK",
    "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc": "NotoSansCJK",
}


class OfficeError(Exception):
    pass


def soffice_path():
    if pathlib.Path(runtime.SOFFICE_APP).exists():
        return runtime.SOFFICE_APP
    found = shutil.which("soffice")
    if not found:
        raise OfficeError("找不到 LibreOffice（soffice），请运行 ./install.sh --render-deps")
    return found


def cjk_font(candidates=None):
    """返回 (字体路径, PDF 字体名前缀)；一款都没有时返回 (None, None)。"""
    for path, name in (candidates or CJK_FONTS).items():
        if pathlib.Path(path).is_file():
            return path, name
    return None, None


def convert(src, to, outdir, timeout=300, soffice=None):
    """把 src 转成 to 格式（如 pdf、docx、pptx），输出到 outdir，返回输出文件路径。"""
    src, outdir = pathlib.Path(src), pathlib.Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    font, _ = cjk_font()
    with tempfile.TemporaryDirectory() as profile:
        if font:
            fonts = pathlib.Path(profile) / "user" / "fonts"
            fonts.mkdir(parents=True)
            (fonts / pathlib.Path(font).name).symlink_to(font)
        args = [soffice or soffice_path(), "-env:UserInstallation=" + pathlib.Path(profile).as_uri(),
                "--headless", "--convert-to", to, "--outdir", str(outdir), str(src)]
        try:
            p = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            raise OfficeError(f"LibreOffice 转换超时（{timeout} 秒）：{src.name}")
        except OSError as err:
            raise OfficeError(f"无法运行 LibreOffice：{err}")
    ext = to.split(":", 1)[0]
    out = outdir / f"{src.stem}.{ext}"
    if p.returncode != 0 or not out.is_file():
        raise OfficeError(f"LibreOffice 转换失败：{src.name} → {ext}：{(p.stdout + p.stderr).strip()[-300:]}")
    return out
