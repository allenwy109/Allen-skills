#!/usr/bin/env bash
# 自检（设计 §11）：单元测试、仓库结构、三个引擎自带的测试。
# 用法：tools/selftest.sh [--quick | --e2e]
#   --quick  只跑单元测试、skill 测试和结构检查；skill 测试缺外部工具时允许跳过
#   --e2e    只跑端到端冒烟（tools/e2e/），包括六类报告的正反固定验收场景
# 引擎测试在临时副本里运行，不会在 vendor/ 下留下产物；需要先完成 ./install.sh --render-deps。
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

QUICK=0
E2E=0
[ "${1:-}" = "--quick" ] && QUICK=1
[ "${1:-}" = "--e2e" ] && E2E=1
# 完整自检时，skill 测试缺外部工具直接算失败（--quick 和 CI 允许跳过）
[ "${QUICK}" = 0 ] && export ALLEN_REQUIRE_TOOLS=1

if [ "${E2E}" = 1 ]; then
  python3 tools/doctor.py >/dev/null || { echo "错误：doctor 没有全部通过，先运行 python3 tools/doctor.py 查看" >&2; exit 1; }
  [ -f tests/report-output-cases.json ] || { echo "错误：缺少六类报告验收夹具" >&2; exit 1; }
  export PATH="/Applications/LibreOffice.app/Contents/MacOS:${PATH}"
  echo "== 端到端冒烟（含六类报告的 6 个正例和 6 个负例）"
  python3 -m unittest discover -s tools/e2e -t . 2>&1 | tee "${TMPDIR:-/tmp}/allen-e2e.log"
  [ "${PIPESTATUS[0]}" = 0 ] || exit 1
  if grep -q "skipped" "${TMPDIR:-/tmp}/allen-e2e.log"; then echo "错误：端到端冒烟被跳过，说明有依赖不可用" >&2; exit 1; fi
  echo "端到端冒烟通过"
  exit 0
fi

echo "== 单元测试"
python3 -m unittest discover -s tools/tests -t .
python3 -m unittest tools.tests.test_research_quality
for d in */scripts/tests; do
  [ -d "${d}" ] || continue
  echo "== ${d}"
  python3 -m unittest discover -s "${d}" -t "${d}"
done
echo "== 仓库结构"
python3 tools/validate.py
if [ "${QUICK}" = 1 ]; then
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
