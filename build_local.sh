#!/usr/bin/env bash
# Rebuilds the site from Notion and serves it at http://localhost:8000.
# Run ./init.sh once first if you haven't set up .venv/.env yet.
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -d .venv ]; then
  echo "No .venv found — run ./init.sh first." >&2
  exit 1
fi

source .venv/bin/activate
python build.py --local
