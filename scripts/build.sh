#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
exec /usr/bin/python3 -u "$ROOT/scripts/build.py" --project "$ROOT" --expected-channel public "$@"
