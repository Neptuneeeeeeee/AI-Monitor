"""Private IPC with Monitor's native Keychain helper. No secret is printed here."""
import hashlib
import os
from core import MonitorError, run
from runtime_config import KEYCHAIN_PREFIX

ALLOWED_SERVICES = {'kimi', 'glm-cn', 'glm-global', 'copilot'}

def fingerprint(value, account=None):
    return hashlib.sha256(str(account or value or '').encode()).hexdigest()[:24]

def keychain(service):
    allowed = {'Claude Code-credentials'} | {KEYCHAIN_PREFIX + s for s in ALLOWED_SERVICES}
    if service not in allowed: raise MonitorError('error', '拒绝读取无关钥匙串条目。')
    helper = os.environ.get('MONITOR_KEYCHAIN_HELPER')
    if not helper: return None
    try:
        rc, out = run([helper, '--keychain-read', service], timeout=25)
    except MonitorError:
        raise MonitorError('unavailable', '钥匙串组件忙或读取超时；并非授权被拒绝，保留上次读数并稍后重试。')
    if rc == 3: raise MonitorError('permission_required', '系统拒绝了 Monitor Keychain 组件的读取。请在设置 → 账号连接 → Claude 点“检查 Claude 读取”；后台不会弹出钥匙串窗口。')
    if rc == 5: raise MonitorError('unavailable', '登录钥匙串已锁定，保留上次读数；解锁后自动恢复，不会弹窗。')
    if rc not in (0, 2): raise MonitorError('unavailable', '钥匙串辅助组件暂不可用，不等同于缺少授权。')
    return out.decode('utf-8') if rc == 0 else None

def own_key(service):
    if service not in ALLOWED_SERVICES: return None
    return keychain(KEYCHAIN_PREFIX + service)
