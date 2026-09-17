"""Kimi Code plan quota. Renewal stays in the official CLI's own credential file.
No browser cookies, copied refresh-token cache, model request, or telemetry.
Protocol reference: MoonshotAI/kimi-code packages/oauth/src (pinned in docs).
"""
import hashlib
import os
from pathlib import Path
import platform
import re
import time
from core import HOME, SUPPORT, MonitorError, atomic_json, read_json, result, window, number, duration_label, executable, run
from credentials import own_key, fingerprint
from kimi_lock import KimiRefreshLock
from network import request_json

USAGE_URL = 'https://api.kimi.com/coding/v1/usages'
REFRESH_URL = 'https://auth.kimi.com/api/oauth/token'
PUBLIC_CLIENT_ID = '17e5f671-d194-4dfb-9706-5516cb48c098'

def kimi_home():
    return Path(os.environ.get('KIMI_CODE_HOME', str(HOME / '.kimi-code'))).expanduser()

def validate_official_origin(home):
    expected = {'KIMI_CODE_BASE_URL': 'https://api.kimi.com/coding/v1', 'KIMI_CODE_OAUTH_HOST': 'https://auth.kimi.com', 'KIMI_OAUTH_HOST': 'https://auth.kimi.com'}
    for key, value in expected.items():
        if os.environ.get(key, value).rstrip('/') != value:
            raise MonitorError('unsupported', '检测到 Kimi 自定义服务地址。本版本不向替代服务发送官方登录凭证。')
    # Only inspect the known managed provider's origin, never execute its config.
    path = home / 'config.toml'
    if path.exists():
        text = path.read_text()
        active = False
        for line in text.splitlines():
            s = line.strip()
            if s.startswith('['): active = bool(re.match(r'\[providers\.[\"\']managed:kimi-code[\"\'](?:\.oauth)?\]', s))
            if active and re.match(r'(base_url|oauth_host)\s*=', s):
                match = re.search(r'=\s*[\"\']([^\"\']+)', s)
                if match and match.group(1).rstrip('/') not in expected.values():
                    raise MonitorError('unsupported', 'Kimi managed provider 使用替代地址；已阻止官方凭证转发。')

def load_cli(home):
    data = read_json(home / 'credentials/kimi-code.json', {})
    if not isinstance(data, dict) or not data.get('access_token') or data.get('revoked_at'):
        raise MonitorError('auth_required', '未找到有效的 Kimi Code 登录。请点击连接，或在官方 CLI 中运行 kimi login。')
    return data

def device_headers(home):
    headers = {'User-Agent': 'Monitor/1.0 (Kimi Code quota monitor)', 'X-Msh-Platform': 'monitor', 'X-Msh-Version': '1.0.0'}
    device = home / 'device_id'
    if device.exists():
        value = device.read_text().strip()
        if re.fullmatch(r'[A-Za-z0-9_-]{8,100}', value): headers['X-Msh-Device-Id'] = value
    ascii_text = lambda x: ''.join(c for c in x if 32 <= ord(c) <= 126) or 'unknown'
    headers['X-Msh-Device-Name'] = ascii_text(platform.node())
    headers['X-Msh-Os-Version'] = ascii_text(platform.release())
    headers['X-Msh-Device-Model'] = ascii_text('macOS ' + platform.mac_ver()[0] + ' ' + platform.machine())
    return headers

def renew(home, previous, force=False):
    """A single grant, under official lock, with reread/CAS and rejected-token guard."""
    with KimiRefreshLock(home) as lock:
        current = load_cli(home)
        if current.get('access_token') != previous.get('access_token'):
            return current
        expires = number(current.get('expires_at'))
        if not force and expires and expires > time.time() + 60: return current
        refresh = current.get('refresh_token')
        if not isinstance(refresh, str) or not refresh:
            raise MonitorError('auth_required', 'Kimi 登录已过期且没有续期凭证，请重新登录。')
        stamp = hashlib.sha256(refresh.encode()).hexdigest()
        guard_path = SUPPORT / 'kimi-refresh-state.json'
        guard = read_json(guard_path, {})
        if guard.get('rejectedHash') == stamp:
            raise MonitorError('auth_required', 'Kimi 的续期凭证已被服务商拒绝。已停止重复重试，请重新 kimi login。')
        try:
            updated = request_json(REFRESH_URL, form={'client_id': PUBLIC_CLIENT_ID, 'grant_type': 'refresh_token', 'refresh_token': refresh}, headers=device_headers(home), timeout=15)
        except MonitorError as error:
            latest = load_cli(home)
            if latest.get('access_token') != current.get('access_token'): return latest
            if error.oauth_code in ('invalid_grant', 'invalid_client', 'unauthorized_client') or error.http_status == 401:
                atomic_json(guard_path, {'rejectedHash': stamp, 'at': time.time()})
                raise MonitorError('auth_required', 'Kimi 续期凭证已失效；已停止重复重试，需在官方 CLI 重新登录。')
            raise
        lock.assert_owned()
        latest = load_cli(home)
        if latest != current:
            # User login or another writer won; never overwrite their new session.
            return latest
        lifetime = number(updated.get('expires_in'))
        if not updated.get('access_token') or not updated.get('refresh_token') or not lifetime or lifetime <= 0:
            raise MonitorError('error', 'Kimi 续期响应缺少必要字段，未改写原登录文件。')
        merged = dict(current)
        for key in ('access_token', 'refresh_token', 'expires_in', 'token_type', 'scope'):
            if key in updated: merged[key] = updated[key]
        merged['expires_at'] = int(time.time() + lifetime)
        atomic_json(home / 'credentials/kimi-code.json', merged)
        atomic_json(guard_path, {'lastSuccess': time.time()})
        return merged

def parse_kimi(payload):
    output = []
    summary = payload.get('usage')
    for index, item in enumerate(payload.get('limits') or []):
        if not isinstance(item, dict): continue
        detail = item.get('detail') or {}
        meta = item.get('window') or {}
        factors = {'TIME_UNIT_SECOND': 1/60, 'TIME_UNIT_MINUTE': 1, 'TIME_UNIT_HOUR': 60, 'TIME_UNIT_DAY': 1440, 'TIME_UNIT_WEEK': 10080}
        factor, duration = factors.get(meta.get('timeUnit')), number(meta.get('duration'))
        minutes = factor * duration if factor is not None and duration is not None else None
        output.append(window('limit-' + str(index), duration_label(minutes), limit=detail.get('limit'), used=detail.get('used'), remaining=detail.get('remaining'), reset=detail.get('resetTime'), minutes=minutes))
    # Official Kimi parser defines the summary field as the plan's weekly pool.
    if isinstance(summary, dict):
        output.append(window('weekly', '每周', limit=summary.get('limit'), used=summary.get('used'), remaining=summary.get('remaining'), reset=summary.get('resetTime'), minutes=10080))
    output.sort(key=lambda x: x['durationMinutes'] or 10**9)
    if not output: raise MonitorError('unsupported', 'Kimi 未返回可识别的套餐额度；没有以 100% 代替。')
    return output

def collect_kimi():
    home = kimi_home()
    explicit = own_key('kimi') or os.environ.get('KIMI_CODE_API_KEY')
    source = 'Kimi Code API Key · 官方 usages' if explicit else 'Kimi Code CLI OAuth · 官方 usages'
    refreshed = False
    validate_official_origin(home)
    if explicit:
        credential = explicit
    else:
        state = load_cli(home)
        expiry = number(state.get('expires_at'))
        if expiry is not None and expiry <= time.time() + 60:
            state = renew(home, state); refreshed = True
        credential = state['access_token']
    headers = device_headers(home)
    headers['Authorization'] = 'Bearer ' + credential
    try:
        payload = request_json(USAGE_URL, headers=headers)
    except MonitorError as error:
        if error.http_status != 401 or explicit: raise
        # A still-valid but rejected token gets at most one coordinated recovery.
        newer = load_cli(home)
        if newer.get('access_token') == credential:
            if refreshed:
                raise MonitorError('auth_required', 'Kimi 更新登录后仍被服务商拒绝；本轮不重复续期，请重新登录。')
            newer = renew(home, newer, force=True); refreshed = True
        credential = newer['access_token']; headers['Authorization'] = 'Bearer ' + credential
        payload = request_json(USAGE_URL, headers=headers)
    user = payload.get('user') or {}
    membership = user.get('membership') or {}
    plan = membership.get('level') if isinstance(membership, dict) else None
    return result('kimi', 'Kimi Code', source, parse_kimi(payload), plan=plan,
                  message='已通过官方 OAuth 接口自动续期。' if refreshed else '',
                  note='套餐单位按服务商返回值计算；不是本地累计 token 的估算。',
                  identity=fingerprint(credential, user.get('id')))
