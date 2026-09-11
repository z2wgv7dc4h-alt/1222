#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e .
if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Edit .env then: source .venv/bin/activate && boo-lab scan && boo-lab studio"
  exit 0
fi
boo-lab scan
echo "http://127.0.0.1:8765"
boo-lab studio --port 8765
