"""Provider-specific plan semantics, intentionally not a token-cost estimator."""
import json
import os
import re
import time
from core import HOME, MonitorError, read_json, result, number, timestamp, window, duration_label, executable, run
from credentials import own_key, keychain, fingerprint
from network import request_json
from rate_limits import http_error, parse_cli_http, has_rate_signal


def parse_claude(payload):
    output = []
    for name, detail in payload.items():
        if not isinstance(detail, dict): continue
        if name == 'five_hour': minutes, label = 300, '当前 5 小时'
        elif name == 'seven_day': minutes, label = 10080, '每周 · 全部模型'
        elif name.startswith('seven_day_'): minutes, label = 10080, '每周 · ' + name[len('seven_day_'):].replace('_', ' ').title()
        else: continue
        if number(detail.get('utilization')) is None: continue
        output.append(window(name, label, used_percent=detail['utilization'], reset=detail.get('resets_at'), minutes=minutes))
    # Official OAuth extra_usage monetary fields use minor units (cents).
    # Only display an explicitly enabled spend cap with both limit and consumption.
    extra = payload.get('extra_usage')
    if isinstance(extra, dict) and extra.get('is_enabled') is True:
        cap, spent = number(extra.get('monthly_limit')), number(extra.get('used_credits'))
        if cap is not None and cap > 0 and spent is not None and spent >= 0:
            currency = str(extra.get('currency') or 'USD').strip().upper()
            if not re.fullmatch(r'[A-Z]{3}', currency): currency = 'USD'
            output.append(window('extra_usage', 'Extra Usage', limit=cap / 100,
                                 used=spent / 100, remaining=max(0, cap-spent) / 100,
                                 unit=currency, currency=currency, kind='extra'))
    return output

def claude_credentials():
    data = read_json(HOME / '.claude/.credentials.json', {})
    if not isinstance(data, dict) or not data.get('claudeAiOauth'):
        if os.environ.get('MONITOR_CLAUDE_KEYCHAIN_ALLOWED') != '1':
            raise MonitorError('permission_required', '请在设置 → 账号连接 → Claude 点“检查 Claude 读取”以启用读取。读取走系统 security 工具，后台不会弹出钥匙串窗口。')
        text = keychain('Claude Code-credentials')
        if text:
            try: data = json.loads(text)
            except ValueError: data = {}
    auth = data.get('claudeAiOauth') if isinstance(data, dict) else None
    if not isinstance(auth, dict) or not auth.get('accessToken'):
        raise MonitorError('auth_required', '未读到 Claude 订阅登录。先授权钥匙串；仍不可用时请在官方 CLI 运行 claude auth login。')
    return auth

def collect_claude():
    state = claude_credentials()
    def fetch(value):
        return request_json('https://api.anthropic.com/api/oauth/usage', headers={'Authorization': 'Bearer ' + value['accessToken'], 'anthropic-beta': 'oauth-2025-04-20'})
    try: payload = fetch(state)
    except MonitorError as error:
        if error.http_status != 401: raise
        # Reread the owning CLI's latest state; never rotate a second refresh chain.
        latest = claude_credentials()
        if latest.get('accessToken') == state.get('accessToken'):
            raise MonitorError('auth_required', 'Claude 的登录凭证需要官方客户端续期。请运行 claude auth login 后刷新；不会反复弹出钥匙串请求。')
        state = latest; payload = fetch(state)
    windows = parse_claude(payload)
    return result('claude', 'Claude Code', '官方 OAuth usage · 本机钥匙串/CLI', windows,
                  plan=state.get('subscriptionType'), status='ok' if windows else 'unsupported',
                  message='' if windows else '账号接口未提供可量化的额度。',
                  identity=fingerprint(state['accessToken']), note='只查询 usage；不发送提示词，不运行模型来触发续期。')

def parse_glm(payload):
    data = payload.get('data') or {}
    if not isinstance(data, dict): raise MonitorError('error', 'GLM 额度响应结构变化，未推算剩余百分比。')
    limits = data.get('limits') or []
    output = []
    factors = {1: 1440, 3: 60, 5: 1, 6: 10080}
    for index, item in enumerate(limits):
        if not isinstance(item, dict) or item.get('type') not in ('TOKENS_LIMIT', 'CREDIT_LIMIT', 'TIME_LIMIT'): continue
        unit, duration = item.get('unit'), number(item.get('number'))
        minutes = factors[unit] * duration if unit in factors and duration and duration > 0 else None
        mcp = item['type'] == 'TIME_LIMIT'
        monthly = mcp and unit == 5 and duration == 1
        if monthly: minutes = None
        label = 'MCP · 本月' if monthly else ('MCP · ' if mcp else '') + duration_label(minutes)
        cap, used, rem = number(item.get('usage')), number(item.get('currentValue')), number(item.get('remaining'))
        percentage = None if cap and cap > 0 and (used is not None or rem is not None) else item.get('percentage')
        reset = timestamp(item.get('nextResetTime'))
        # Reject impossible 5h reset values rather than applying invented timezone fixes.
        if minutes == 300 and reset and reset > time.time() + 5 * 3600 + 60: reset = None
        output.append(window(str(index), label, used_percent=percentage, limit=cap, used=used, remaining=rem,
                             reset=reset, minutes=minutes, unit='MCP' if mcp else 'plan credits'))
    output.sort(key=lambda w: w['durationMinutes'] or 10**9)
    return output

def collect_glm(region):
    key = own_key('glm-' + region)
    if not key:
        names = ('BIGMODEL_API_KEY', 'ZHIPU_API_KEY', 'ZHIPUAI_API_KEY', 'GLM_API_KEY') if region == 'cn' else ('Z_AI_API_KEY', 'ZAI_API_KEY')
        key = next((os.environ[n] for n in names if os.environ.get(n)), None)
    if not key: raise MonitorError('auth_required', '请在设置中选择中国/国际区域，并保存对应的 GLM Coding Plan API Key。密钥存放于本机钥匙串。')
    host = 'open.bigmodel.cn' if region == 'cn' else 'api.z.ai'
    payload = request_json('https://' + host + '/api/monitor/usage/quota/limit', headers={'Authorization': 'Bearer ' + key})
    if payload.get('success') is False:
        raise MonitorError('permission_required', 'GLM 未授权套餐额度查询，请检查所选区域、API Key 与 Coding Plan 资格。')
    windows = parse_glm(payload)
    return result('glm', 'GLM Coding Plan', ('BigModel 中国' if region == 'cn' else 'Z.ai 国际') + ' · 官方 quota/limit', windows,
                  status='ok' if windows else 'unsupported', message='' if windows else '接口未提供可识别的 Coding Plan 窗口。',
                  identity=fingerprint(key), note='按接口实际的 5 小时、周、MCP 等窗口显示；两个区域的凭证不混用。')

def parse_copilot(payload):
    snapshots = payload.get('quota_snapshots') or payload.get('quotaSnapshots') or {}
    output = []
    for key, label in [('premium_interactions', 'Premium · 每月'), ('chat', 'Chat · 计费周期'), ('completions', 'Completions · 计费周期')]:
        item = snapshots.get(key) or snapshots.get('premiumInteractions' if key == 'premium_interactions' else key)
        if not isinstance(item, dict): continue
        unlimited = item.get('unlimited') is True
        cap = number(item.get('entitlement'))
        # Sentinel -1 and absent quotas are billing placeholders, not 0% / 100%.
        if cap is not None and cap < 0 and not unlimited: continue
        percent = item.get('percent_remaining', item.get('percentRemaining'))
        if number(percent) is None and not unlimited: continue
        output.append(window(key, label, remaining_percent=percent, unlimited=unlimited,
                             limit=cap, remaining=item.get('remaining'),
                             reset=payload.get('quota_reset_date', payload.get('quotaResetDate')), kind='monthly' if key == 'premium_interactions' else None))
    return output

def collect_copilot():
    key = own_key('copilot')
    headers = {'Authorization': 'token ' + key, 'Accept': 'application/json', 'Editor-Version': 'vscode/1.96.2', 'Editor-Plugin-Version': 'copilot-chat/0.26.7', 'User-Agent': 'GitHubCopilotChat/0.26.7', 'X-Github-Api-Version': '2025-04-01'} if key else None
    if key:
        payload = request_json('https://api.github.com/copilot_internal/user', headers=headers)
    else:
        binary = executable('gh')
        if not binary: raise MonitorError('unavailable', '请先用 GitHub CLI 登录，或配置可访问 Copilot 额度的账号。')
        args = [binary, 'api', '--include', '--hostname', 'github.com', '/copilot_internal/user', '-H', 'Accept: application/json',
                '-H', 'Editor-Version: vscode/1.96.2', '-H', 'Editor-Plugin-Version: copilot-chat/0.26.7',
                '-H', 'User-Agent: GitHubCopilotChat/0.26.7', '-H', 'X-Github-Api-Version: 2025-04-01']
        rc, out = run(args, timeout=18)
        status, response_headers, payload = parse_cli_http(out)
        if status >= 400 or rc:
            if not status:
                fallback = str(payload.get('status', ''))
                status = int(fallback) if fallback.isdigit() else 0
            if status: raise http_error(status, response_headers, payload)
            if has_rate_signal(payload): raise http_error(429, response_headers, payload)
            raise MonitorError('network_error', 'GitHub 官方额度查询未完成，已安排稍后重试。')
        if has_rate_signal(payload): raise http_error(429, response_headers, payload)
        if not payload: raise MonitorError('error', 'Copilot 返回无法识别的响应。')
    windows = parse_copilot(payload)
    token_billing = bool(payload.get('token_based_billing', payload.get('tokenBasedBilling')))
    return result('copilot', 'GitHub Copilot', 'GitHub CLI · Copilot 额度接口', windows,
                  plan=payload.get('copilot_plan', payload.get('copilotPlan')), status='ok' if windows else 'unsupported',
                  message='' if windows else ('当前账号采用 token 计费，接口没有提供可量化的套餐百分比。' if token_billing else '当前接口未提供可量化额度；不伪造 5 小时或每周窗口。'),
                  note='计费周期按官方响应显示。不限量不等同于 100% 剩余。')
