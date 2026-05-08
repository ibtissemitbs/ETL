#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="$ROOT/.venv/bin/python"

if [ ! -x "$PY" ]; then
  echo "Python environment not found: $PY"
  echo "Run:"
  echo "  python -m venv .venv"
  echo "  .venv/bin/python -m pip install -r requirements.txt"
  exit 1
fi

cd "$ROOT"
echo "Starting ETL Platform backend..."
echo "API:  http://127.0.0.1:8000"
echo "Docs: http://127.0.0.1:8000/docs"
echo "Press CTRL+C to stop."
echo

"$PY" -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
