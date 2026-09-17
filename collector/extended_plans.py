"""Additional plan adapters. Never run inference to measure or refresh a quota.

Field contracts/research sources: docs/PLAN_RESEARCH_2026_09.md.
Unknown or contradictory data produces no invented zero/100 percent allowance.
"""
import base64
import json
import re
import time
from pathlib import Path
from core import HOME, SUPPORT, MonitorError, number, timestamp, window, result, read_json, executable, run
from credentials import own_key
from network import request_json
from local_plan_store import read_app_value

NEW_IDS = {'cursor', 'minimax', 'windsurf', 'kiro'}
DB_PATHS = {
    'cursor': 'Library/Application Support/Cursor/User/globalStorage/state.vscdb',
    'windsurf': 'Library/Application Support/Windsurf/User/globalStorage/state.vscdb',
}
MINIMAX_ENDPOINTS = {
    'cn': 'https://www.minimaxi.com/v1/token_plan/remains',
    'global': 'https://www.minimax.io/v1/token_plan/remains',
}


def safe_text(value, limit=60):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        return None
    if not re.fullmatch(r'[\w .+()/\-]+', value, flags=re.UNICODE):
        return None
    return value.strip()


def percent(value):
    n = number(value)
    return n if n is not None and 0 <= n <= 100 else None


def counted(wid, label, cap, used=None, remaining=None, **kwargs):
    if any(raw is not None and number(raw) is None for raw in (cap, used, remaining)):
        return None
    cap, used, remaining = number(cap), number(used), number(remaining)
    if cap is None or cap <= 0:
        return None
    if used is not None and used < 0 or remaining is not None and (remaining < 0 or remaining > cap):
        return None
    if used is None and remaining is None:
        return None
    if used is not None and remaining is not None and abs(max(0, cap - used) - remaining) > max(0.01, cap * 0.000001):
        return None
    rem = remaining if remaining is not None else max(0, cap - used)
    return window(wid, label, limit=cap, remaining=rem, **kwargs)


def checked_result(pid, name, source, windows, plan=None, note=None):
    return result(pid, name, source, windows, plan=plan, note=note,
                  status='ok' if windows else 'unsupported',
                  message='' if windows else '此账号响应未提供可识别的数值额度；请查看官方用量页。')


# Cursor --------------------------------------------------------------------
def cursor_cookie(token, now=None):
    now = time.time() if now is None else now
    if not isinstance(token, str) or len(token) > 16384 or not re.fullmatch(r'[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+', token):
        raise MonitorError('auth_required', 'Cursor 登录状态不可用，请在 Cursor 应用重新登录。')
    try:
        part = token.split('.')[1]
        claims = json.loads(base64.urlsafe_b64decode(part + '=' * (-len(part) % 4)))
        uid = claims['sub'].split('|')[-1]
        expiry = number(claims.get('exp'))
        if not re.fullmatch(r'[A-Za-z0-9_.-]{1,200}', uid) or expiry is None or expiry <= now + 60:
            raise ValueError('invalid or expired')
    except (ValueError, KeyError, TypeError, AttributeError):
        raise MonitorError('auth_required', 'Cursor 登录凭证已过期或格式变化；请由官方应用完成续期。')
    # Claims are used only to format the session, not to assert verified identity.
    return 'WorkosCursorSessionToken=' + uid + '%3A%3A' + token


def parse_cursor(payload):
    individual = payload.get('individualUsage')
    plan = individual.get('plan') if isinstance(individual, dict) else None
    if not isinstance(plan, dict) or plan.get('enabled') is not True:
        return []
    # A zero-capacity account may still report 0 percent used for every pool.
    # That describes no positive allowance, not 100 percent remaining. An
    # explicit invalid/nonpositive limit overrides percentage placeholders;
    # absent limits are allowed for genuine percentage-only responses.
    if 'limit' in plan:
        cap = number(plan['limit'])
        if cap is None or cap <= 0:
            return []
    reset = payload.get('billingCycleEnd')
    windows = []
    total = percent(plan.get('totalPercentUsed'))
    if total is not None:
        windows.append(window('cursor-monthly', '套餐 · 本月', used_percent=total, reset=reset, kind='monthly'))
    elif plan.get('totalPercentUsed') is None:
        counted_total = counted('cursor-monthly', '套餐 · 本月', plan.get('limit'), used=plan.get('used'),
                                remaining=plan.get('remaining'), reset=reset, kind='monthly', unit='plan credits')
        if counted_total:
            windows.append(counted_total)
    # Separate pools are never averaged or summed into a fictional total.
    for key, wid, label in [('autoPercentUsed', 'cursor-auto', 'Auto 额度池 · 本月'),
                            ('apiPercentUsed', 'cursor-api', 'API 额度池 · 本月')]:
        used = percent(plan.get(key))
        if used is not None:
            windows.append(window(wid, label, used_percent=used, reset=reset, kind='monthly'))
    return windows


def collect_cursor():
    token, _ = read_app_value(HOME / DB_PATHS['cursor'], 'cursorAuth/accessToken')
    if not token:
        raise MonitorError('auth_required', '请先在 Cursor 官方应用登录，再启用此套餐。')
    payload = request_json('https://cursor.com/api/usage-summary', headers={
        'Cookie': cursor_cookie(token), 'Accept': 'application/json'})
    value = checked_result('cursor', 'Cursor', 'Cursor 应用登录 · 官方 usage-summary', parse_cursor(payload),
                           safe_text(payload.get('membershipType')),
                           '显示官方本月包含额度；不把团队余额或按量付费上限并入个人套餐。不续期凭据、不扫描浏览器。')
    usage = payload.get('individualUsage')
    plan = usage.get('plan') if isinstance(usage, dict) else None
    if not value['windows'] and isinstance(plan, dict) and number(plan.get('limit')) == 0:
        value['message'] = '已连接 Cursor；官方套餐上限为 0，没有可计算的套餐剩余百分比。'
        value['note'] = '接口的 0% 已使用不是 100% 可用；不将零额度池、免费账号或按量消费预算当成有剩余的订阅套餐。'
    return value


# MiniMax -------------------------------------------------------------------
def minimax_settings():
    value = read_json(SUPPORT / 'plan-connections.json', {})
    if not isinstance(value, dict) or value.get('minimaxRegion', 'cn') not in MINIMAX_ENDPOINTS:
        raise MonitorError('auth_required', 'MiniMax 区域配置无效，请在账号连接中重新选择。')
    return value


def parse_minimax(payload):
    data = payload.get('data', payload)
    if not isinstance(data, dict):
        raise MonitorError('error', 'MiniMax 返回结构变化，未推算额度。')
    for envelope in [payload, data]:
        base = envelope.get('base_resp')
        if isinstance(base, dict) and number(base.get('status_code')) not in (None, 0):
            status = number(base.get('status_code'))
            if status == 1004:
                raise MonitorError('auth_required', 'MiniMax 拒绝此订阅 Key；请核对区域与 Key 类型。')
            if status == 2062:
                raise MonitorError('auth_required', '该 MiniMax Key 未对应有效 Token Plan；积分余额不代表套餐额度。')
            raise MonitorError('unavailable', 'MiniMax 套餐查询暂不可用，请在官方平台检查。')
    windows = []
    items = data.get('model_remains')
    if isinstance(items, list):
        # Prefer unified quota when available; never add model lanes sharing one pool.
        valid = [x for x in items if isinstance(x, dict)]
        unified = [x for x in valid if str(x.get('model_name', '')).lower() == 'general']
        selected = unified or [x for x in valid if re.search(r'(?i)text|mini.?max.?m[0-9]|^m[0-9]', str(x.get('model_name', '')))]
        for index, item in enumerate(selected[:12]):
            label = safe_text(item.get('model_name'), 40) or '套餐'
            for suffix, prefix, start_key, end_key, minutes in [
                ('5h', 'current_interval_', 'start_time', 'end_time', 300),
                ('weekly', 'current_weekly_', 'weekly_start_time', 'weekly_end_time', 10080)]:
                # Status 3 lanes are unavailable/unlimited, not measured 100%.
                if number(item.get(prefix + 'status')) == 3:
                    continue
                rem = percent(item.get(prefix + 'remaining_percent'))
                end, start = timestamp(item.get(end_key)), timestamp(item.get(start_key))
                if suffix == '5h' and end is not None and start is not None:
                    duration = (end - start) / 60
                    if not 0 < duration <= 44640:
                        continue
                    minutes = int(round(duration))
                kwargs = dict(reset=end, minutes=minutes, unit='plan quota')
                title = label + (' · 每周' if suffix == 'weekly' else ' · 当前窗口')
                wid = 'minimax-' + str(index) + '-' + suffix
                if rem is not None:
                    windows.append(window(wid, title, remaining_percent=rem, **kwargs))
                elif item.get(prefix + 'remaining_percent') is None:
                    # Despite the API name, usage_count represents REMAINING quota.
                    w = counted(wid, title, item.get(prefix + 'total_count'), remaining=item.get(prefix + 'usage_count'), **kwargs)
                    if w:
                        windows.append(w)
        return windows
    services = data.get('services')
    if isinstance(services, list):
        for index, item in enumerate(services[:24]):
            if not isinstance(item, dict) or not re.search(r'(?i)general|text.?generation', str(item.get('service_type', ''))):
                continue
            window_type = str(item.get('window_type', '')).strip().lower()
            minutes = {'5 hours': 300, '5h': 300, 'weekly': 10080, 'week': 10080}.get(window_type)
            if minutes is None:
                continue
            w = counted('minimax-service-' + str(index), '套餐 · ' + ('每周' if minutes == 10080 else '当前 5 小时'),
                        item.get('limit'), used=item.get('usage'), minutes=minutes, unit='plan quota')
            if w:
                # percent in this legacy service shape is USED, not remaining.
                used_pct = percent(item.get('percent'))
                if used_pct is not None and abs(w['remainingPercent'] - (100 - used_pct)) > 1:
                    continue
                windows.append(w)
    return windows


def collect_minimax():
    region = minimax_settings().get('minimaxRegion', 'cn')
    key = own_key('minimax-' + region)
    if not key:
        raise MonitorError('auth_required', '在账号连接中展开 MiniMax，选择区域并保存订阅 Key；不是普通按量计费 Key。')
    if len(key) > 8192 or not re.fullmatch(r'[!-~]+', key):
        raise MonitorError('auth_required', 'MiniMax Key 格式无效，请重新保存。')
    payload = request_json(MINIMAX_ENDPOINTS[region], headers={'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'})
    data = payload.get('data', payload)
    name = next((safe_text(data.get(k)) for k in ('current_subscribe_title', 'plan_name', 'combo_title', 'current_plan_title')
                 if isinstance(data, dict) and safe_text(data.get(k))), None)
    return checked_result('minimax', 'MiniMax', 'MiniMax ' + ('中国' if region == 'cn' else '国际') + ' · 官方 Token Plan 用量',
                          parse_minimax(payload), name,
                          '5 小时与周窗口按响应显示；积分和并发限制不冒充套餐余量。不跨区域尝试 Key。')


# Windsurf: local cached quota only ------------------------------------------
def parse_windsurf(payload):
    if not isinstance(payload, dict):
        return []
    windows = []
    quota = payload.get('quotaUsage')
    if isinstance(quota, dict):
        for key, wid, label, minutes, reset_key in [
            ('dailyRemainingPercent', 'windsurf-daily', '每日额度 · 缓存', 1440, 'dailyResetAtUnix'),
            ('weeklyRemainingPercent', 'windsurf-weekly', '每周额度 · 缓存', 10080, 'weeklyResetAtUnix')]:
            rem = percent(quota.get(key))
            if rem is not None:
                windows.append(window(wid, label, remaining_percent=rem, minutes=minutes, reset=quota.get(reset_key)))
        return windows
    usage = payload.get('usage')
    if isinstance(usage, dict):
        for total, used, rem, wid, label in [
            ('messages', 'usedMessages', 'remainingMessages', 'windsurf-messages', '消息额度 · 缓存'),
            ('flowActions', 'usedFlowActions', 'remainingFlowActions', 'windsurf-actions', '操作额度 · 缓存')]:
            w = counted(wid, label, usage.get(total), used=usage.get(used), remaining=usage.get(rem), unit='credits')
            if w:
                windows.append(w)
    return windows


def collect_windsurf():
    raw, modified = read_app_value(HOME / DB_PATHS['windsurf'], 'windsurf.settings.cachedPlanInfo')
    if not raw:
        raise MonitorError('auth_required', '请先打开 Windsurf 并登录，让官方应用更新套餐缓存。')
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        raise MonitorError('error', 'Windsurf 本地套餐缓存格式变化，未推算额度。')
    if not isinstance(data, dict):
        raise MonitorError('error', 'Windsurf 本地套餐缓存格式变化，未推算额度。')
    windows = parse_windsurf(data)
    value = checked_result('windsurf', 'Windsurf', 'Windsurf 官方应用 · 本地缓存（非实时）', windows,
                           safe_text(data.get('planName')),
                           '仅为官方应用缓存。时间是状态文件修改时间，不是额度实测时间；打开 Windsurf 后才可能更新。')
    value['fetchedAt'] = min(modified, time.time())
    if windows:
        value.update(status='stale', message='本地缓存，非实时额度。')
    return value


# Kiro: official, non-inference slash command --------------------------------
def parse_kiro(raw):
    text = re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]|\x1b\][^\x07]*(?:\x07|\x1b\\)', '', raw)
    lower = text.lower()
    if any(s in lower for s in ['not logged in', 'login required', 'failed to initialize auth portal', 'oauth error']):
        raise MonitorError('auth_required', '请先使用官方 kiro-cli login 登录。')
    if 'could not retrieve usage information' in lower:
        raise MonitorError('unavailable', 'Kiro 官方 CLI 本次未取得用量，请稍后重试。')
    plan_match = re.search(r'(?im)Plan:[ \t]*([^|\r\n]{1,60})', text) or re.search(r'\b(KIRO[ \t]+(?:FREE|PRO(?:[ \t]+(?:PLUS|MAX))?))\b', text)
    plan = safe_text(plan_match.group(1).strip()) if plan_match else None
    # Require actual numerator AND denominator, never infer free-tier defaults.
    match = re.search(r'\((\d[\d,]*(?:\.\d+)?)\s+of\s+(\d[\d,]*(?:\.\d+)?)\s+covered in plan\)', text, re.I)
    windows = []
    if match:
        w = counted('kiro-monthly', '套餐 Credits · 本月', match.group(2).replace(',', ''),
                    used=match.group(1).replace(',', ''), kind='monthly', unit='credits')
        if w:
            windows.append(w)
    value = checked_result('kiro', 'Kiro', '官方 kiro-cli /usage', windows, plan,
                           '只显示 CLI 明确报告的本月套餐 Credits；不合并赠额、超额预算或上下文占用。不推测重置时区。')
    if 'estimated usage' in lower and windows:
        for quota in windows:
            quota['label'] += '（官方估计）'
        value.update(status='partial', message='官方 CLI 报告的估计用量，非最终账单。')
        value['note'] = '官方 CLI 将此数据标为 Estimated Usage；仅显示其套餐计数，不将其视为最终账单。'
    return value


def collect_kiro():
    binary = executable('kiro-cli')
    if not binary:
        raise MonitorError('unavailable', '未找到 kiro-cli；请先安装官方 CLI 并登录。')
    # Exact slash command, no prompt, no trust-all-tools, no resume, no retry with inference.
    rc, raw = run([binary, 'chat', '--no-interactive', '/usage'], timeout=25)
    text = raw.decode('utf-8', 'replace')
    value = parse_kiro(text)
    if rc:
        raise MonitorError('unavailable', 'Kiro CLI 查询未正常退出；未将不完整输出当作成功结果。')
    return value
