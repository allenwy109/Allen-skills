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
(cd "${WORK}/thinkcell-charts" && NODE_PATH="${RT}/vendor/report-forge/node_modules" TC_BROWSER_PATH="${CHROME}" node tests/check_html_browser.cjs)

echo "== onepager"
copy_engine onepager
run_py_tests onepager

echo "自检全部通过"
