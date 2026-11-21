#!/usr/bin/env bash
# Starter Dope Wars - BFT edition på Linux. Opretter .venv-linux ved første kørsel.
# Brug:  ./run-linux.sh           spillet
#        ./run-linux.sh --test    alle tests (headless)
set -euo pipefail
cd "$(dirname "$0")"
if [ ! -x .venv-linux/bin/python ]; then
  python3 -m venv .venv-linux
  .venv-linux/bin/pip install -q -r requirements-linux.txt
fi
if [ "${1:-}" = "--test" ]; then
  QT_QPA_PLATFORM=offscreen BFT_DATA_DIR="$(mktemp -d)" exec .venv-linux/bin/python -m unittest test_game test_events test_lan test_release test_ui
fi
exec .venv-linux/bin/python app.py "$@"
