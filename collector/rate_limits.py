"""Shared, redacted HTTP/CLI rate-limit handling (RFC 9110 Retry-After).

All intervals here are query-control information, NEVER coding-plan consumption.
No raw response body, token, or account identifier is returned to UI/logs.
"""
import datetime
import email.utils
import json
import re
import time
from core import MonitorError, number

RATE_MESSAGE = '服务商暂时限制额度查询，已暂停请求；到时自动检查。'


def retry_delay(headers, now=None):
    now = time.time() if now is None else now
    h = {str(k).lower(): str(v).strip() for k, v in (headers or {}).items()}
    delays = [0.0]
    value = h.get('retry-after', '')
    if re.fullmatch(r'[0-9]+', value):
        delays.append(float(value))
    elif value:
        try:
            date = email.utils.parsedate_to_datetime(value)
            if date.tzinfo is None: date = date.replace(tzinfo=datetime.timezone.utc)
            deadline = date.timestamp()
            delays.append(deadline - now)
            # A skewed local clock must not shorten the server's requested wait.
            if h.get('date'):
                server_date = email.utils.parsedate_to_datetime(h['date'])
                delays.append(deadline - server_date.timestamp())
        except (ValueError, TypeError, OverflowError): pass
    if h.get('x-ratelimit-remaining') == '0':
        reset = number(h.get('x-ratelimit-reset'))
        if reset is not None: delays.append(reset - now)
    if h.get('anthropic-ratelimit-requests-remaining') == '0':
        raw = h.get('anthropic-ratelimit-requests-reset')
        try: delays.append(datetime.datetime.fromisoformat(raw.replace('Z', '+00:00')).timestamp() - now)
        except (AttributeError, ValueError, TypeError, OverflowError): pass
    # Deliberately no one-hour cap: a valid longer Retry-After is authoritative.
    return max(delays)


def has_rate_signal(payload):
    if not isinstance(payload, dict): return False
    code = payload.get('httpStatus', payload.get('status', payload.get('code')))
    if str(code) == '429': return True
    kind = payload.get('type')
    if kind in ('rate_limit_error', 'rate_limit_exceeded', 'too_many_requests'): return True
    text = str(payload.get('message') or '').lower()
    if re.search(r'\b(?:http\s*429|429\s+too many|too many requests|secondary rate limit|api rate limit exceeded|rate[ _-]limit(?:ed|[ _-]exceeded|[ _-]error))\b', text): return True
    return any(has_rate_signal(payload.get(key)) for key in ('error', 'data') if isinstance(payload.get(key), dict))


def http_error(status, headers=None, payload=None):
    payload = payload if isinstance(payload, dict) else {}
    h = {str(k).lower(): str(v) for k, v in (headers or {}).items()}
    delay = retry_delay(h)
    if status == 429 or (status == 403 and (h.get('x-ratelimit-remaining') == '0' or has_rate_signal(payload))):
        return MonitorError('rate_limited', RATE_MESSAGE, http_status=status, retry_after=delay)
    oauth = payload.get('error')
    oauth = oauth if isinstance(oauth, str) and oauth in ('invalid_grant', 'invalid_client', 'unauthorized_client') else None
    if status == 401: return MonitorError('auth_required', '服务商拒绝当前登录凭证，请检查对应官方客户端登录。', http_status=status, oauth_code=oauth, retry_after=delay)
    if status == 403: return MonitorError('permission_required', '服务商拒绝访问，请检查账号权限或套餐；不是额度耗尽。', http_status=status, oauth_code=oauth, retry_after=delay)
    if status >= 500: return MonitorError('network_error', '额度接口暂时不可用，已暂停重试。', http_status=status, retry_after=delay)
    return MonitorError('error', '额度接口返回 HTTP %d，未记录响应正文。' % status, http_status=status, oauth_code=oauth, retry_after=delay)


def rpc_error(payload):
    payload = payload if isinstance(payload, dict) else {}
    if has_rate_signal(payload):
        data = payload.get('data') if isinstance(payload.get('data'), dict) else {}
        delay = max(0, number(data.get('retryAfterSeconds')) or number(data.get('retry_after')) or 0)
        return MonitorError('rate_limited', RATE_MESSAGE, http_status=429, retry_after=delay)
    code = str(payload.get('httpStatus', payload.get('status', '')))
    if code.isdigit() and 400 <= int(code) <= 599: return http_error(int(code), payload=payload)
    text = str(payload.get('message') or '').lower()
    if any(word in text for word in ('unauthorized', 'not authenticated', 'login required', 'not logged in')):
        return MonitorError('auth_required', '官方客户端尚未完成有效登录，请检查登录状态。')
    return MonitorError('network_error', '官方额度查询暂时未完成，已安排稍后重试。')


def parse_cli_http(raw):
    """Parse gh api --include output; retain only rate-control headers in memory."""
    text = raw.decode('utf-8', 'replace') if isinstance(raw, bytes) else str(raw)
    status, headers = 0, {}
    while text.startswith('HTTP/'):
        match = re.match(r'^HTTP/\S+\s+(\d{3})[^\r\n]*\r?\n', text)
        if not match: break
        end = re.search(r'\r?\n\r?\n', text)
        if not end: break
        status = int(match.group(1)); headers = {}
        for line in text[match.end():end.start()].splitlines():
            key, sep, value = line.partition(':')
            if sep and key.lower() in ('retry-after', 'date', 'x-ratelimit-remaining', 'x-ratelimit-reset'):
                headers[key.lower()] = value.strip()
        text = text[end.end():].lstrip('\r\n')
    try: payload = json.loads(text)
    except (ValueError, TypeError): payload = {}
    return status, headers, payload if isinstance(payload, dict) else {}
