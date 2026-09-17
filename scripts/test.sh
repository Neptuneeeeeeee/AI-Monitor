#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PYTHONDONTWRITEBYTECODE=1
/usr/bin/python3 "$ROOT/scripts/audit_public.py"
/usr/bin/python3 "$ROOT/scripts/test_python.py"
exec /usr/bin/swift run --package-path "$ROOT" --scratch-path "$HOME/Library/Caches/AIMonitor/Public/CoreChecks" -j 2 MonitorCoreChecks
