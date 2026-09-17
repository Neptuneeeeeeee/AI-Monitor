#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
exec /usr/bin/python3 "$ROOT/scripts/install.py" --project "$ROOT" --channel public "$@"
