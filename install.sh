#!/usr/bin/env bash
# 安装 Allen 的方法论 skill 系统，以及 zerox.lock 里固定版本的 zerox skill。
#
# 用法：
#   ./install.sh                     安装到 ~/.claude/skills（复制）
#   ./install.sh --target DIR        安装到其他目录
#   ./install.sh --link              用软链接代替复制（在本仓库里改 skill 立即生效）
#   ./install.sh --no-zerox          只装本仓库的 skill
#   ./install.sh --forge-deps        额外为 zerox-consulting-report-forge 安装 npm 依赖和字体
#   ./install.sh --remove-old        删除旧版 skill（consulting-analysis 等三个旧名字）
#   ./install.sh --force             覆盖目标目录里不是本脚本装的同名 skill
#
# 环境变量：
#   ZEROX_REPO   改用其他 zerox 仓库地址（例如自己的 fork）
#   CACHE_DIR    zerox 源码缓存位置，默认 ~/.cache/allen-skills
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET="${HOME}/.claude/skills"
MODE="copy"
WITH_ZEROX=1
FORGE_DEPS=0
REMOVE_OLD=0
FORCE=0
MARKER=".installed-by-allen-skills"
OLD_NAMES="consulting-analysis management-toolkit personal-effectiveness"

while [ $# -gt 0 ]; do
  case "$1" in
    --target) TARGET="$2"; shift 2 ;;
    --link) MODE="link"; shift ;;
    --no-zerox) WITH_ZEROX=0; shift ;;
    --forge-deps) FORGE_DEPS=1; shift ;;
    --remove-old) REMOVE_OLD=1; shift ;;
    --force) FORCE=1; shift ;;
    -h|--help) sed -n '2,17p' "$0"; exit 0 ;;
    *) echo "未知参数：$1" >&2; exit 2 ;;
  esac
done

mkdir -p "$TARGET"
installed=()
skipped=()

# 把一个 skill 目录装到 TARGET/<name>
place() {
  local src="$1" name="$2" dest="$TARGET/$2"
  if [ -e "$dest" ] || [ -L "$dest" ]; then
    if [ -L "$dest" ] || [ -f "$dest/$MARKER" ] || [ "$FORCE" = 1 ]; then
      rm -rf "$dest"
    else
      skipped+=("$name（目标已存在且不是本脚本安装的，用 --force 覆盖）")
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

# 1. 本仓库的 skill：根目录下含 SKILL.md 的目录
for d in "$REPO_DIR"/*/; do
  d="${d%/}"
  [ -f "$d/SKILL.md" ] || continue
  place "$d" "$(basename "$d")"
done

# 2. zerox skill，按 zerox.lock 固定版本
if [ "$WITH_ZEROX" = 1 ]; then
  # shellcheck disable=SC1091
  . "$REPO_DIR/zerox.lock"
  repo="${ZEROX_REPO:-$ZEROX_REPO_DEFAULT}"
  cache="${CACHE_DIR:-${XDG_CACHE_HOME:-$HOME/.cache}/allen-skills}/zerox-skills"
  mkdir -p "$cache"
  if [ ! -d "$cache/.git" ]; then
    git -C "$cache" init -q
    git -C "$cache" remote add origin "$repo"
  else
    git -C "$cache" remote set-url origin "$repo"
  fi
  if [ "$(git -C "$cache" rev-parse -q --verify HEAD 2>/dev/null || true)" != "$ZEROX_COMMIT" ]; then
    echo "下载 zerox-skills @ ${ZEROX_COMMIT:0:7} ……"
    GIT_LFS_SKIP_SMUDGE=1 git -C "$cache" fetch -q --depth 1 origin "$ZEROX_COMMIT"
    GIT_LFS_SKIP_SMUDGE=1 git -C "$cache" checkout -q --force FETCH_HEAD
  fi
  for s in $ZEROX_SKILLS; do
    if [ -f "$cache/$s/SKILL.md" ]; then
      place "$cache/$s" "$s"
    else
      skipped+=("$s（zerox 该版本里没有这个 skill）")
    fi
  done
  if [ "$FORGE_DEPS" = 1 ] && [ -d "$TARGET/zerox-consulting-report-forge" ]; then
    echo "安装 report-forge 依赖（需要 Node.js 20+、Python 3.10+、Chrome 或 Playwright Chromium、Poppler）……"
    (cd "$TARGET/zerox-consulting-report-forge" && npm ci && npm run setup-fonts)
  fi
fi

# 3. 旧版 skill
for o in $OLD_NAMES; do
  if [ -e "$TARGET/$o" ]; then
    if [ "$REMOVE_OLD" = 1 ]; then
      rm -rf "${TARGET:?}/$o"
      echo "已删除旧版：$o"
    else
      echo "提示：$TARGET/$o 是旧版 skill，已被 lib-* 取代。建议运行 ./install.sh --remove-old 删除，避免重复触发。"
    fi
  fi
done

echo "安装到：$TARGET（方式：$MODE）"
echo "已安装 ${#installed[@]} 个：${installed[*]}"
if [ ${#skipped[@]} -gt 0 ]; then
  echo "跳过："
  printf '  - %s\n' "${skipped[@]}"
fi
