"""Cooperate with Kimi Code's proper-lockfile directory lock (5 s stale).

The live sentinel is <KIMI_CODE_HOME>/oauth/kimi-code.lock. A 1-second
heartbeat keeps the lock alive while the HTTPS request is in progress.
Never refresh without the lock. Never remove someone else's replacement lock.
"""
import contextlib
import os
from pathlib import Path
import threading
import time
from core import MonitorError

class KimiRefreshLock:
    def __init__(self, home, wait_seconds=8):
        self.path = Path(home) / 'oauth/kimi-code.lock'
        self.wait_seconds = wait_seconds
        self.stop = threading.Event()
        self.lost = False
        self.inode = None
        self.thread = None
    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        deadline = time.monotonic() + self.wait_seconds
        while True:
            try:
                self.path.mkdir(mode=0o700)
                self.inode = self.path.stat().st_ino
                break
            except FileExistsError:
                # Only stale empty locks may be recovered; fresh CLI locks are respected.
                try:
                    first = self.path.stat()
                    if time.time() - first.st_mtime > 30:
                        second = self.path.stat()
                        if (first.st_ino, first.st_mtime_ns) == (second.st_ino, second.st_mtime_ns):
                            self.path.rmdir()
                            continue
                except (FileNotFoundError, OSError): pass
                if time.monotonic() >= deadline:
                    raise MonitorError('unavailable', 'Kimi 官方客户端正在更新登录状态，本轮跳过刷新以避免冲突。')
                time.sleep(0.15)
        self.thread = threading.Thread(target=self._heartbeat, daemon=True)
        self.thread.start()
        return self
    def _heartbeat(self):
        while not self.stop.wait(1):
            try:
                if self.path.stat().st_ino != self.inode:
                    self.lost = True; return
                os.utime(self.path, None)
            except OSError:
                self.lost = True; return
    def assert_owned(self):
        try: owned = self.path.stat().st_ino == self.inode
        except OSError: owned = False
        if self.lost or not owned:
            raise MonitorError('error', 'Kimi 登录锁已变化；未覆盖官方客户端的新凭证。')
    def __exit__(self, *args):
        self.stop.set()
        if self.thread: self.thread.join(timeout=2)
        with contextlib.suppress(OSError):
            if self.path.stat().st_ino == self.inode: self.path.rmdir()
