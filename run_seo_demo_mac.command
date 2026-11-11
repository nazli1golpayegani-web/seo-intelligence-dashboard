#!/bin/bash
# Local-only SEO Intelligence demo launcher. No Google or AI credentials needed.
set -euo pipefail

pause_on_exit() {
  echo
  read -r -p "Press Enter to close this window..." _ || true
}
trap pause_on_exit EXIT

HERE="$(cd "$(dirname "$0")" && pwd)"
if [[ -f "$HERE/app.py" ]]; then
  ROOT="$HERE"
else
  APP_FILE="$(find "$HERE" -maxdepth 4 -type f -name 'app.py' -not -path '*/.venv/*' -print -quit)"
  if [[ -z "$APP_FILE" ]]; then
    echo "ERROR: app.py was not found beside this launcher or in a subfolder."
    echo "Put this script inside the folder extracted from the SEO Intelligence ZIP."
    exit 1
  fi
  ROOT="$(dirname "$APP_FILE")"
fi
cd "$ROOT"
echo "Using project folder: $ROOT"

# Preserve original source files while repairing uploads that were flattened.
for module in ai analytics auth connectors demo reports storage; do
  if [[ -f "${module}.py" && ! -f "src/${module}.py" ]]; then
    mkdir -p src
    cp "${module}.py" "src/${module}.py"
  fi
done
if [[ -d src && ! -f src/__init__.py ]]; then
  touch src/__init__.py
fi
for testname in test_app test_core; do
  if [[ -f "${testname}.py" && ! -f "tests/${testname}.py" ]]; then
    mkdir -p tests
    cp "${testname}.py" "tests/${testname}.py"
  fi
done
for font in DejaVuSans.ttf DejaVuSans-Bold.ttf; do
  if [[ -f "$font" && ! -f "assets/fonts/$font" ]]; then
    mkdir -p assets/fonts
    cp "$font" "assets/fonts/$font"
  fi
done

if [[ ! -f src/demo.py || ! -f src/analytics.py ]]; then
  echo "ERROR: Required src/ modules are missing. Check the ZIP contents."
  exit 1
fi

PYTHON_BIN=""
for candidate in python3.12 python3.13 python3.11 python3; do
  if command -v "$candidate" >/dev/null 2>&1; then
    if "$candidate" -c 'import sys; assert sys.version_info >= (3, 11)' >/dev/null 2>&1; then
      PYTHON_BIN="$candidate"
      break
    fi
  fi
done
if [[ -z "$PYTHON_BIN" ]]; then
  echo "ERROR: Python 3.11+ is required. Install Python 3.12 and try again."
  exit 1
fi

echo "Python: $($PYTHON_BIN --version)"
if [[ ! -f .venv/bin/activate ]]; then
  "$PYTHON_BIN" -m venv .venv
fi
source .venv/bin/activate

if [[ -f requirements-tested.txt ]]; then
  echo "Installing exact tested package versions..."
  python -m pip install -r requirements-tested.txt
elif [[ -f requirements.txt ]]; then
  echo "Installing supported package versions..."
  python -m pip install -r requirements.txt
else
  echo "ERROR: Neither requirements-tested.txt nor requirements.txt exists."
  exit 1
fi

mkdir -p .streamlit
# Explicitly restrict the server to the user's computer; the demo starts enabled in app.py.
echo
printf 'Dashboard URL: http://127.0.0.1:8501\n'
echo "Use the sidebar toggle 'Synthetic demo mode' (enabled by default)."
echo "Press Ctrl+C in this window to stop the server."
echo
python -m streamlit run app.py --server.address 127.0.0.1 --server.port 8501
