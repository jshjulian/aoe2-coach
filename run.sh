#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
if [[ ! -x "$ROOT/.venv/bin/python" ]]; then
  echo "Python environment missing. See docs/setup.md for explicit setup; startup never installs packages." >&2
  exit 1
fi
exec "$ROOT/.venv/bin/python" "$ROOT/app.py" "$@"
