"""Local runtime and normalized quota records. No raw response logging."""
from __future__ import annotations
import contextlib
import datetime as dt
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import threading
import time

from runtime_config import HOME, SUPPORT
CHILDREN = set()
CHILDREN_LOCK = threading.Lock()

class MonitorError(Exception):
    def __init__(self, status, message, source='', http_status=None, oauth_code=None, retry_after=0):
        super().__init__(message)
        self.status, self.message, self.source = status, message, source
        self.http_status, self.oauth_code, self.retry_after = http_status, oauth_code, retry_after

def number(value):
    if value is None or isinstance(value, bool): return None
    try:
        n = float(value)
        return n if math.isfinite(n) else None
    except (ValueError, TypeError, OverflowError): return None

def timestamp(value):
    n = number(value)
    if n is not None: return n / 1000 if n > 10**11 else n
    if not isinstance(value, str): return None
    try:
        result = dt.datetime.fromisoformat(value.strip().replace('Z', '+00:00'))
        if result.tzinfo is None: result = result.replace(tzinfo=dt.timezone.utc)
        return result.timestamp()
    except (ValueError, OverflowError): return None

def duration_label(minutes, fallback='服务商窗口'):
    if minutes == 300: return '当前 5 小时'
    if minutes == 10080: return '每周'
    if minutes is None or minutes <= 0: return fallback
    if minutes % 1440 == 0: return '%g 天窗口' % (minutes / 1440)
    if minutes % 60 == 0: return '%g 小时窗口' % (minutes / 60)
    return '%g 分钟窗口' % minutes

def window(wid, label, *, remaining_percent=None, used_percent=None, limit=None, remaining=None, used=None, reset=None, minutes=None, unit='plan', unlimited=False, kind=None, currency=None):
    cap, rem, consumed = number(limit), number(remaining), number(used)
    p = number(remaining_percent)
    if p is None and number(used_percent) is not None: p = 100 - number(used_percent)
    if p is None and cap is not None and cap > 0:
        if rem is not None and rem >= 0: p = 100 * rem / cap
        elif consumed is not None and consumed >= 0: p = 100 * (1 - consumed / cap)
    return {'id': wid, 'label': label,
            'remainingPercent': min(100., max(0., p)) if p is not None and not unlimited else None,
            'resetAt': timestamp(reset), 'durationMinutes': number(minutes), 'unit': unit,
            'remaining': rem, 'limit': cap, 'isUnlimited': bool(unlimited), 'kind': kind, 'currency': currency}

def read_json(path, default=None):
    path = Path(path)
    try:
        if path.stat().st_size > 4 * 1024 * 1024: return default
        return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError, UnicodeDecodeError): return default
    except PermissionError: raise MonitorError('permission_required', '无法读取所需本地文件，请检查当前用户的文件权限。')

def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, name = tempfile.mkstemp(prefix='.' + path.name + '.', dir=str(path.parent))
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, 'w') as f:
            json.dump(value, f, ensure_ascii=False, allow_nan=False, separators=(',', ':'))
            f.write('\n'); f.flush(); os.fsync(f.fileno())
        os.replace(name, str(path))
    finally:
        with contextlib.suppress(FileNotFoundError): os.unlink(name)

def stop_child(p):
    if p.poll() is None:
        with contextlib.suppress(ProcessLookupError): os.killpg(p.pid, signal.SIGTERM)
        try: p.wait(timeout=2)
        except subprocess.TimeoutExpired:
            with contextlib.suppress(ProcessLookupError): os.killpg(p.pid, signal.SIGKILL)
            p.wait(timeout=2)
    with CHILDREN_LOCK: CHILDREN.discard(p)

def run(args, timeout=10, input_data=None):
    try:
        p = subprocess.Popen(args, stdin=subprocess.PIPE if input_data is not None else subprocess.DEVNULL,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True,
                             cwd=str(SUPPORT if SUPPORT.exists() else HOME), env={**os.environ, 'NO_COLOR': '1'})
    except FileNotFoundError: raise MonitorError('unavailable', '未找到所需官方客户端或本地辅助程序。')
    with CHILDREN_LOCK: CHILDREN.add(p)
    try:
        stdout, _stderr = p.communicate(input=input_data, timeout=timeout)
        if len(stdout) > 4 * 1024 * 1024: raise MonitorError('error', '客户端输出超过安全解析范围。')
        return p.returncode, stdout
    except subprocess.TimeoutExpired: raise MonitorError('network_error', '官方客户端查询超时，已终止本次查询进程。')
    finally: stop_child(p)

def executable(name):
    import shutil
    paths = {'kimi': [HOME / '.kimi-code/bin/kimi'], 'codex': [Path('/opt/homebrew/bin/codex')], 'claude': [HOME / '.local/bin/claude']}
    for p in paths.get(name, []) + [Path('/opt/homebrew/bin') / name, Path('/usr/local/bin') / name]:
        if p.is_file() and os.access(p, os.X_OK): return str(p)
    return shutil.which(name)

def result(pid, name, source, windows, *, plan=None, note=None, message='', status='ok', identity=None):
    return {'id': pid, 'name': name, 'status': status, 'source': source, 'message': message,
            'plan': plan, 'fetchedAt': time.time(), 'attemptedAt': time.time(),
            'windows': windows, 'note': note, '_identity': identity}
