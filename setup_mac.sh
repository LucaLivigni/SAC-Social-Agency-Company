#!/bin/zsh
set -e

echo ""
echo "SAC Studio — setup macOS"
echo "------------------------"

PYTHON_BIN=""
if command -v python3.12 >/dev/null 2>&1; then
  PYTHON_BIN="$(command -v python3.12)"
elif command -v python3 >/dev/null 2>&1 && python3 - <<'PY' >/dev/null 2>&1
import sys
raise SystemExit(0 if sys.version_info >= (3,10) else 1)
PY
then
  PYTHON_BIN="$(command -v python3)"
elif command -v brew >/dev/null 2>&1; then
  echo "Python recente non trovato. Installo Python 3.12 con Homebrew..."
  brew install python@3.12
  PYTHON_BIN="$(brew --prefix python@3.12)/bin/python3.12"
else
  echo "Serve Python 3.10 o superiore."
  exit 1
fi

echo "Uso $($PYTHON_BIN --version)"
rm -rf .venv
"$PYTHON_BIN" -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if [ ! -f .env ]; then cp .env.example .env; fi

echo ""
echo "Setup completato. Avvia con ./run_mac.sh"
