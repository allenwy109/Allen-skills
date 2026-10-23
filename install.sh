#!/usr/bin/env bash
# 安装 Allen 的方法论 skill 系统和运行时（_allen-runtime：vendor/ 里固定版本的三个渲染引擎和 tools/）。
#
# 用法：
#   ./install.sh                     安装到 Claude Code（~/.claude/skills，复制）
#   ./install.sh --codex             安装到 Codex（~/.codex/skills，复制）
#   ./install.sh --both              同时安装到 Claude Code 和 Codex
#   ./install.sh --claude            显式安装到 Claude Code
#   ./install.sh --target DIR        安装到其他目录
#   ./install.sh --link              用软链接代替复制（在本仓库里改 skill 立即生效）
#   ./install.sh --render-deps       额外安装出成品所需的依赖：LibreOffice 等系统工具、Python 虚拟环境、
#                                    Playwright Chromium、报告引擎的 npm 依赖与字体，并生成能力探测任务
#   ./install.sh --force             覆盖目标目录里不是本脚本装的同名 skill 或运行时
#
# 环境变量：
#   ALLEN_VENV   Python 虚拟环境位置，默认 ~/.cache/allen-skills/venv
#
# 运行时（_allen-runtime）：复制模式下是 vendor/ 和 tools/ 的副本；--link 模式下是指向本仓库的软链接。
# 复制模式重新安装会清掉运行时里的 npm 依赖和探测结果，之后需要重新运行 --render-deps。
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLATFORM="claude"
TARGET=""
MODE="copy"
FORCE=0
RENDER_DEPS=0
RUNTIME_NAME="_allen-runtime"
# 与 tools/lib/runtime.py 的 venv_python() 保持一致
VENV="${ALLEN_VENV:-${XDG_CACHE_HOME:-$HOME/.cache}/allen-skills/venv}"
MARKER=".installed-by-allen-skills"

while [ $# -gt 0 ]; do
  case "$1" in
    --target) TARGET="$2"; shift 2 ;;
    --claude) PLATFORM="claude"; shift ;;
    --codex) PLATFORM="codex"; shift ;;
    --both) PLATFORM="both"; shift ;;
    --link) MODE="link"; shift ;;
    --render-deps) RENDER_DEPS=1; shift ;;
    --force) FORCE=1; shift ;;
    -h|--help) sed -n '2,16p' "$0"; exit 0 ;;
    *) echo "未知参数：$1" >&2; exit 2 ;;
  esac
done

if [ -n "$TARGET" ]; then
  TARGETS=("$TARGET")
else
  case "$PLATFORM" in
    claude) TARGETS=("${HOME}/.claude/skills") ;;
    codex) TARGETS=("${CODEX_HOME:-${HOME}/.codex}/skills") ;;
    both) TARGETS=("${HOME}/.claude/skills" "${CODEX_HOME:-${HOME}/.codex}/skills") ;;
  esac
fi

# 把一个 skill 目录装到 TARGET/<name>
place() {
  local src="$1" name="$2" dest="$CURRENT_TARGET/$2"
  if [ -e "$dest" ] || [ -L "$dest" ]; then
    if [ -L "$dest" ] || [ -f "$dest/$MARKER" ] || [ "$FORCE" = 1 ]; then
      rm -rf "$dest"
    else
      skipped+=("${name}（目标已存在且不是本脚本安装的，用 --force 覆盖）")
      return
    fi
  fi
  if [ "$MODE" = "link" ]; then
    ln -s "$src" "$dest"
  else
    cp -R "$src" "$dest"
    rm -rf "$dest/.git"
    echo "source=$src" > "$dest/$MARKER"
  fi
  installed+=("$name")
}

# 安装运行时 TARGET/_allen-runtime
place_runtime() {
  local dest="${CURRENT_TARGET}/${RUNTIME_NAME}"
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
    cp -R "${REPO_DIR}/vendor" "${REPO_DIR}/tools" "${dest}/"
    find "${dest}" -type d \( -name node_modules -o -name .font-venv -o -name __pycache__ -o -name .probe-task \) \
      -prune -exec rm -rf {} +
    find "${dest}" -type f -name .probe.json -delete
    echo "source=${REPO_DIR}" > "${dest}/${MARKER}"
  fi
  installed+=("${RUNTIME_NAME}")
}

# 安装平台入口：Claude Code 为 /allen-*；Codex 自定义 prompt 为 /prompts:allen-*。
place_entries() {
  local platform="$1" entry_dir src_dir src name dest
  if [ "$platform" = "claude" ]; then
    entry_dir="${CURRENT_TARGET%/skills}/commands"
  elif [ "$platform" = "codex" ]; then
    entry_dir="${CURRENT_TARGET%/skills}/prompts"
  else
    return 0
  fi
  src_dir="${REPO_DIR}/commands/${platform}"
  mkdir -p "$entry_dir"
  for src in "$src_dir"/*.md; do
    name="$(basename "$src")"
    dest="$entry_dir/$name"
    if [ -e "$dest" ] || [ -L "$dest" ]; then
      if [ -L "$dest" ] || grep -q "installed-by-allen-skills" "$dest" 2>/dev/null || [ "$FORCE" = 1 ]; then
        rm -f "$dest"
      else
        skipped+=("${name}（应用入口已存在且不是本脚本安装的，用 --force 覆盖）")
        continue
      fi
    fi
    if [ "$MODE" = "link" ]; then
      ln -s "$src" "$dest"
    else
      cp "$src" "$dest"
    fi
    installed+=("entry:${name%.md}")
  done
}

# 安装出成品所需的依赖（设计 §9）
render_deps() {
  local rt="${CURRENT_TARGET}/${RUNTIME_NAME}"
  if [ ! -d "${rt}/vendor/report-forge" ]; then
    echo "错误：没有找到 ${rt}/vendor/report-forge，无法安装渲染依赖。" >&2
    return 1
  fi
  if [ "$(uname -s)" = "Darwin" ]; then
    if ! command -v brew >/dev/null 2>&1; then
      echo "错误：macOS 安装渲染依赖需要 Homebrew（https://brew.sh）。" >&2
      return 1
    fi
    echo "[1/5] 系统工具（Homebrew）：poppler、tesseract、tesseract-lang、pandoc、LibreOffice ……"
    for f in poppler tesseract tesseract-lang pandoc; do
      brew list --formula "${f}" >/dev/null 2>&1 || brew install "${f}"
    done
    [ -d /Applications/LibreOffice.app ] || brew install --cask libreoffice
  else
    echo "[1/5] 检查 Linux 系统工具 ……"
    missing=()
    for c in pdfinfo pdftotext pdftoppm pdffonts tesseract pandoc soffice; do
      command -v "$c" >/dev/null 2>&1 || missing+=("$c")
    done
    if command -v tesseract >/dev/null 2>&1; then
      tesseract_langs="$(tesseract --list-langs 2>/dev/null || true)"
      case $'\n'"${tesseract_langs}"$'\n' in
        *$'\nchi_sim\n'*) ;;
        *) missing+=("tesseract-ocr-chi-sim") ;;
      esac
    fi
    if [ ${#missing[@]} -gt 0 ]; then
      echo "错误：Linux 缺少系统工具：${missing[*]}" >&2
      echo "Debian/Ubuntu 可安装：sudo apt-get install poppler-utils tesseract-ocr tesseract-ocr-chi-sim pandoc libreoffice fonts-noto-cjk" >&2
      return 1
    fi
  fi

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
  (cd "${rt}/vendor/report-forge" && npm ci && npx playwright install chromium && npm run setup-fonts)

  echo "[5/5] 报告引擎能力探测任务 ……"
  rm -rf "${rt}/.probe-task"
  (cd "${rt}/vendor/report-forge" && node scripts/probe_capabilities.cjs "${rt}/.probe-task")
  echo "下一步（必须由 Claude Code 或 Codex 在会话里完成看图）："
  echo "  1. 打开 ${rt}/.probe-task/vision-challenge.png，按引擎要求把看到的内容写成 response.json："
  echo '     {"code":"图中六字符","shape_left_to_right":["颜色 形状","颜色 形状","颜色 形状"]}'
  echo "  2. 运行 python3 ${rt}/tools/record_probe.py --response <response.json>"
  echo "  3. 运行 python3 ${rt}/tools/doctor.py 确认全部通过"
}

for CURRENT_TARGET in "${TARGETS[@]}"; do
  mkdir -p "$CURRENT_TARGET"
  installed=()
  skipped=()
  for d in "$REPO_DIR"/*/; do
    d="${d%/}"
    [ -f "$d/SKILL.md" ] || continue
    place "$d" "$(basename "$d")"
  done
  place_runtime

  entry_platform=""
  if [ -z "$TARGET" ] && [ "$CURRENT_TARGET" = "${HOME}/.claude/skills" ]; then
    entry_platform="claude"
  elif [ -z "$TARGET" ] && [ "$CURRENT_TARGET" = "${CODEX_HOME:-${HOME}/.codex}/skills" ]; then
    entry_platform="codex"
  fi
  place_entries "$entry_platform"

  if [ "${RENDER_DEPS}" = 1 ]; then
    render_deps
  fi

  echo "安装到：${CURRENT_TARGET}（方式：${MODE}）"
  echo "已安装 ${#installed[@]} 个：${installed[*]}"
  if [ ${#skipped[@]} -gt 0 ]; then
    echo "跳过："
    printf '  - %s\n' "${skipped[@]}"
  fi
done
