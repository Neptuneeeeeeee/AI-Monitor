"""Bounded reads of specific official-app state keys; never changes the source DB."""
import os
from contextlib import closing
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from core import MonitorError

ALLOWED_KEYS = {'cursorAuth/accessToken', 'windsurf.settings.cachedPlanInfo'}
# Cursor's state database may include large unrelated app state. On APFS we
# clone blocks, then query only one allowlisted row in the disposable clone.
MAX_DATABASE_BYTES = 2 * 1024 * 1024 * 1024
MAX_FALLBACK_COPY_BYTES = 128 * 1024 * 1024
MAX_VALUE_BYTES = 256 * 1024


def snapshot_copy(source, target):
    if source.is_symlink():
        raise MonitorError('unavailable', '拒绝符号链接形式的应用数据库。')
    if sys.platform == 'darwin':
        # cp -c requests an APFS copy-on-write clone; no source sidecars are opened.
        try:
            done = subprocess.run(['/bin/cp', '-c', str(source), str(target)],
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
            if done.returncode == 0:
                os.chmod(target, 0o600)
                return
        except (OSError, subprocess.TimeoutExpired):
            pass
        if target.exists():
            target.unlink()
    if source.stat().st_size > MAX_FALLBACK_COPY_BYTES:
        raise MonitorError('unavailable', '当前磁盘不支持快速快照且应用数据库较大，未读取聊天内容或改写原数据库。')
    shutil.copyfile(source, target)
    os.chmod(target, 0o600)


def file_state(paths):
    result = []
    for p in paths:
        try:
            s = p.stat()
            result.append((s.st_ino, s.st_size, s.st_mtime_ns))
        except FileNotFoundError:
            result.append(None)
    return result


def read_app_value(database, key):
    """Copy a stable DB/WAL snapshot to an owner-only temporary directory.

    SQLite may recover/checkpoint the private copy, never the official database.
    Only the whitelisted ItemTable row is queried. No chat rows are parsed/exported.
    """
    if key not in ALLOWED_KEYS:
        raise MonitorError('error', '拒绝读取无关的应用状态条目。')
    database = Path(database)
    if not database.is_file():
        raise MonitorError('unavailable', '未找到官方应用的本地状态，请先安装并登录对应应用。')
    paths = [database, Path(str(database) + '-wal')]
    try:
        for _ in range(2):
            before = file_state(paths)
            if not before[0] or sum(s[1] for s in before if s) > MAX_DATABASE_BYTES:
                raise MonitorError('unavailable', '应用状态文件过大或正在切换，已停止读取。')
            with tempfile.TemporaryDirectory(prefix='ai-monitor-plan-') as directory:
                os.chmod(directory, 0o700)
                copy = Path(directory) / 'state.sqlite3'
                for source, state, suffix in zip(paths, before, ('', '-wal')):
                    if state:
                        target = Path(str(copy) + suffix)
                        snapshot_copy(source, target)
                if before != file_state(paths):
                    continue
                with closing(sqlite3.connect(str(copy), timeout=0.25)) as connection:
                    connection.execute('PRAGMA trusted_schema=OFF')
                    connection.execute('PRAGMA query_only=ON')
                    row = connection.execute(
                        'SELECT value FROM ItemTable WHERE key = ? LIMIT 1', (key,)).fetchone()
                if row is None:
                    return None, max(s[2] for s in before if s) / 1e9
                value = row[0]
                if isinstance(value, bytes):
                    if len(value) > MAX_VALUE_BYTES:
                        raise ValueError('oversize value')
                    # ASCII UTF-16LE would otherwise decode as UTF-8 with embedded NULs.
                    encoding = 'utf-16-le' if len(value) % 2 == 0 and value[1::2] and set(value[1::2]) == {0} else 'utf-8-sig'
                    value = value.decode(encoding)
                if not isinstance(value, str) or len(value.encode('utf-8')) > MAX_VALUE_BYTES or '\x00' in value:
                    raise ValueError('invalid state value')
                return value, max(s[2] for s in before if s) / 1e9
        raise MonitorError('unavailable', '官方应用正在更新状态，请稍后重试。')
    except PermissionError:
        raise MonitorError('permission_required', '当前用户无法读取此应用的状态；不会自动修改系统权限。')
    except (OSError, sqlite3.Error, UnicodeError, ValueError):
        raise MonitorError('unavailable', '应用状态不可读取或格式已变化；未推算额度。')
