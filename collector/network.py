"""HTTPS allowlist for read-only plan endpoints and the Kimi OAuth renewal endpoint."""
import json
import socket
import ssl
import urllib.error
import urllib.parse
import urllib.request
from core import MonitorError
from rate_limits import http_error, has_rate_signal

ALLOWED_REMOTE = {
    ('cursor.com', '/api/usage-summary'),
    ('www.minimaxi.com', '/v1/token_plan/remains'),
    ('www.minimax.io', '/v1/token_plan/remains'),
    ('api.kimi.com', '/coding/v1/usages'), ('auth.kimi.com', '/api/oauth/token'),
    ('api.anthropic.com', '/api/oauth/usage'), ('api.github.com', '/copilot_internal/user'),
    ('open.bigmodel.cn', '/api/monitor/usage/quota/limit'), ('api.z.ai', '/api/monitor/usage/quota/limit'),
}

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise MonitorError('error', '额度接口发生重定向；为保护凭证，已停止请求。')

def validate_url(url, local=False):
    parts = urllib.parse.urlsplit(url)
    if local:
        if parts.hostname != '127.0.0.1' or parts.scheme not in ('http', 'https') or not parts.path.startswith('/exa.language_server_pb.LanguageServerService/'):
            raise MonitorError('error', '拒绝非本机额度服务。')
    elif parts.scheme != 'https' or (parts.hostname, parts.path) not in ALLOWED_REMOTE or parts.port not in (None, 443) or parts.username or parts.password or parts.query:
        raise MonitorError('error', '拒绝未授权的凭证目标地址。')

def request_json(url, *, headers=None, form=None, body=None, timeout=12, local=False):
    validate_url(url, local)
    h = {'Accept': 'application/json', 'User-Agent': 'Monitor/1.0 (local quota monitor)'}
    h.update(headers or {})
    data = None
    if form is not None:
        h['Content-Type'] = 'application/x-www-form-urlencoded'; data = urllib.parse.urlencode(form).encode()
    elif body is not None:
        h['Content-Type'] = 'application/json'; data = json.dumps(body).encode()
    # Only verified loopback services may use their self-signed local certificate.
    context = ssl._create_unverified_context() if local else ssl.create_default_context()
    handlers = [NoRedirect(), urllib.request.HTTPSHandler(context=context)]
    if local: handlers.append(urllib.request.ProxyHandler({}))
    opener = urllib.request.build_opener(*handlers)
    request = urllib.request.Request(url, headers=h, data=data)
    try:
        with opener.open(request, timeout=timeout) as response:
            raw = response.read(2 * 1024 * 1024 + 1)
            if len(raw) > 2 * 1024 * 1024: raise MonitorError('error', '额度响应过大，已中止解析。')
            obj = json.loads(raw)
            if not isinstance(obj, dict): raise MonitorError('error', '服务商返回了无法识别的额度结构。')
            if has_rate_signal(obj):
                raise http_error(429, response.headers, obj)
            return obj
    except urllib.error.HTTPError as error:
        try: payload = json.loads(error.read(32768))
        except (ValueError, UnicodeDecodeError): payload = {}
        raise http_error(error.code, error.headers, payload)
    except (urllib.error.URLError, TimeoutError, socket.timeout, ssl.SSLError, ConnectionError):
        raise MonitorError('network_error', '网络连接或 TLS 校验失败；请检查网络后重试。')
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise MonitorError('error', '额度接口未返回有效 JSON；未把未知结果当成可用额度。')
