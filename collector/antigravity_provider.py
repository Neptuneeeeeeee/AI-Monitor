"""Read quota from this user's official Antigravity local service only.

Do not import browser sessions, remote OAuth tokens or model-availability
placeholders. Numeric lsof output is essential: otherwise macOS resolves
127.0.0.1 to 'localhost' and a live service disappears from the matcher.
"""
import os
import re
import shlex
import time
from core import MonitorError, number, result, run, window, SUPPORT, read_json, atomic_json
from network import request_json

PREFIX = '/exa.language_server_pb.LanguageServerService/'
APP_ROOTS = ('/Applications/Antigravity.app/', '/Applications/Antigravity IDE.app/')


def bucket_minutes(bucket):
    words = str(bucket.get('displayName', '')) + ' ' + str(bucket.get('bucketId', ''))
    words = re.sub(r'[_-]+', ' ', words).lower()
    if re.search(r'\bweek(?:ly)?\b', words):
        return 10080
    if re.search(r'\b(?:5\s*h(?:our)?s?|five\s+hours?)\b', words):
        return 300
    return None


def parse_antigravity(payload):
    root = payload.get('response') or payload.get('summary') or payload
    output = []
    if isinstance(root, dict):
        for gi, group in enumerate(root.get('groups') or []):
            if not isinstance(group, dict):
                continue
            group_name = str(group.get('displayName') or '额度组')[:80]
            if group_name.lower() == 'gemini models':
                group_name = 'Gemini'
            elif group_name.lower() in ('claude and gpt models', 'claude & gpt models'):
                group_name = 'Claude'  # User-facing alias only; quota IDs and measurements are unchanged.
            for bi, bucket in enumerate(group.get('buckets') or []):
                if not isinstance(bucket, dict) or bucket.get('disabled'):
                    continue
                fraction = number(bucket.get('remainingFraction'))
                nested = bucket.get('remaining') or {}
                if fraction is None and isinstance(nested, dict):
                    fraction = number(nested.get('remainingFraction'))
                    if fraction is None and nested.get('case') == 'remainingFraction':
                        fraction = number(nested.get('value'))
                if fraction is None or not 0 <= fraction <= 1:
                    continue
                minutes = bucket_minutes(bucket)
                name = ('Session' if minutes == 300 else 'Weekly' if minutes == 10080 else
                        str(bucket.get('displayName') or bucket.get('bucketId') or '服务商窗口')[:100])
                # Keep groups distinguishable in the narrow view; never collapse
                # different model pools into an invented all-account quota.
                output.append(window('group-%d-%d' % (gi, bi), group_name + ' · ' + name,
                                     remaining_percent=fraction * 100,
                                     reset=bucket.get('resetTime'), minutes=minutes))
    if output:
        return output
    status = payload.get('userStatus') or payload
    if not isinstance(status, dict):
        return []
    config = status.get('cascadeModelConfigData') or {}
    models = status.get('clientModelConfigs') or (config.get('clientModelConfigs') if isinstance(config, dict) else []) or []
    for index, model in enumerate(models):
        if not isinstance(model, dict):
            continue
        quota = model.get('quotaInfo') or {}
        if not isinstance(quota, dict):
            continue
        fraction = number(quota.get('remainingFraction'))
        if fraction is None or not 0 <= fraction <= 1:
            continue
        output.append(window('model-' + str(index), str(model.get('label') or '模型额度')[:100],
                             remaining_percent=fraction * 100, reset=quota.get('resetTime')))
    return output


def parse_listeners(text):
    ports = []
    for line in text.splitlines():
        # Wildcard listeners accept loopback; non-loopback interface-only binds
        # are not candidates. Connections always target 127.0.0.1, never DNS.
        match = re.fullmatch(r'n(?:127\.0\.0\.1|0\.0\.0\.0|\*):([0-9]+)', line.strip())
        if match and 0 < int(match.group(1)) < 65536:
            port = int(match.group(1))
            if port not in ports:
                ports.append(port)
    return ports


def official_processes(text):
    found = []
    for line in text.splitlines():
        parts = line.strip().split(None, 1)
        if len(parts) != 2 or not parts[0].isdigit():
            continue
        path = parts[1]
        if not path.startswith(APP_ROOTS):
            continue
        if not re.fullmatch(r'language_server(?:_macos(?:_arm|_x64)?)?', path.rsplit('/', 1)[-1]):
            continue
        found.append((int(parts[0]), path))
    return found


def csrf_for(command, executable):
    # ps does not quote an executable path containing spaces. Remove its known
    # prefix before parsing the remaining arguments, instead of shlex'ing it.
    if not command.strip().startswith(executable):
        return None
    try:
        args = shlex.split(command.strip()[len(executable):])
    except ValueError:
        return None
    for i, arg in enumerate(args):
        if arg.startswith('--csrf_token='):
            return arg.split('=', 1)[1] or None
        if arg == '--csrf_token' and i + 1 < len(args):
            return args[i + 1] or None
    return None


def local_servers():
    rc, out = run(['/bin/ps', '-U', str(os.getuid()), '-ww', '-o', 'pid=,comm='], timeout=4)
    if rc:
        raise MonitorError('unavailable', '无法检查当前用户的 Antigravity 进程，请稍后重试。')
    processes = official_processes(out.decode('utf-8', 'replace'))
    servers, missing_auth = [], False
    for pid, executable in processes[:3]:
        rc, args = run(['/bin/ps', '-p', str(pid), '-ww', '-o', 'command='], timeout=4)
        csrf = csrf_for(args.decode('utf-8', 'replace'), executable) if rc == 0 else None
        if not csrf:
            missing_auth = True
            continue
        rc, listeners = run(['/usr/sbin/lsof', '-nP', '-a', '-p', str(pid), '-iTCP', '-sTCP:LISTEN', '-Fn'], timeout=4)
        if rc not in (0, 1):
            continue
        for port in parse_listeners(listeners.decode('utf-8', 'replace'))[:4]:
            candidate = (port, csrf)
            if candidate not in servers:
                servers.append(candidate)
    if not servers and missing_auth:
        raise MonitorError('unavailable', 'Antigravity 已运行，但本地服务的认证信息尚未就绪；请等待启动完成后刷新。')
    if not servers and processes:
        raise MonitorError('unavailable', 'Antigravity 已运行，但尚未找到它的本机监听端口；请等待启动完成后刷新。')
    return servers[:6]


def collect_antigravity():
    servers = local_servers()
    if not servers:
        raise MonitorError('unavailable', '请打开并登录 Antigravity；关闭官方应用后本地额度服务不可用。')
    deadline = time.monotonic() + 18
    last_error = None
    attempts = 0
    remembered = read_json(SUPPORT / 'antigravity-endpoint.json', {})
    servers.sort(key=lambda item: item[0] != remembered.get('port'))
    # Find the richer summary before accepting a legacy model-only response.
    for methods in (('RetrieveUserQuotaSummary',), ('GetUserStatus', 'GetCommandModelConfigs')):
        for port, csrf in servers:
            headers = {'Connect-Protocol-Version': '1', 'X-Codeium-Csrf-Token': csrf}
            schemes = ('http', 'https') if remembered.get('port') == port and remembered.get('scheme') == 'http' else ('https', 'http')
            for scheme in schemes:
                for method in methods:
                    left = deadline - time.monotonic()
                    if left <= 0 or attempts >= 8:
                        break
                    try:
                        attempts += 1
                        payload = request_json('%s://127.0.0.1:%d%s%s' % (scheme, port, PREFIX, method),
                                               body={}, headers=headers, local=True, timeout=min(2.0, left))
                        windows = parse_antigravity(payload)
                        if windows:
                            atomic_json(SUPPORT / 'antigravity-endpoint.json', {'port': port, 'scheme': scheme})
                            return result('antigravity', 'Antigravity', '官方应用 · 本机额度服务', windows,
                                          note='Gemini 与 Claude 分别显示（Claude 为本地显示别名）。菜单栏取实际五小时池的最低余量，不用月/周额度代替。')
                    except MonitorError as error:
                        # Never fan out to other ports/protocols after explicit throttling.
                        if error.status == 'rate_limited' or error.retry_after > 0: raise
                        last_error = error
    if last_error and last_error.status in ('auth_required', 'permission_required', 'rate_limited'):
        raise MonitorError(last_error.status, 'Antigravity 本地额度接口暂时拒绝查询，请检查官方应用。', http_status=last_error.http_status, retry_after=last_error.retry_after)
    raise MonitorError('unavailable', '已发现 Antigravity 本地服务，但它没有返回可用配额；请在官方应用中打开额度页面后重试。')
