#!/usr/bin/env bash
# Starter Dope Wars - BFT edition på Linux. Opretter .venv-linux ved første kørsel.
# Brug:  ./run-linux.sh           spillet
#        ./run-linux.sh --test    alle tests (headless)
set -euo pipefail
cd "$(dirname "$0")"
if [ ! -x .venv-linux/bin/python ]; then
  python3 -m venv .venv-linux
fi
requirements_hash="$(sha256sum requirements-linux.txt)"
if [ ! -f .venv-linux/bft-requirements.sha256 ] || [ "$(cat .venv-linux/bft-requirements.sha256)" != "$requirements_hash" ]; then
  .venv-linux/bin/pip install -q -r requirements-linux.txt
  printf '%s\n' "$requirements_hash" > .venv-linux/bft-requirements.sha256
fi
if [ "${1:-}" = "--test" ]; then
  bft_test_data="$(mktemp -d)"
  trap 'rm -rf -- "$bft_test_data"' EXIT
  QT_QPA_PLATFORM=offscreen BFT_DATA_DIR="$bft_test_data" .venv-linux/bin/python -m unittest test_game test_events test_lan test_release test_ui test_platform
  exit 0
fi
exec .venv-linux/bin/python app.py "$@"
