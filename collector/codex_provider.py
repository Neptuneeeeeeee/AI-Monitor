"""Official Codex app-server read-only JSON-RPC. No model turn is created."""
import contextlib
import json
import os
import selectors
import subprocess
import time
from core import MonitorError, SUPPORT, HOME, CHILDREN, CHILDREN_LOCK, stop_child, executable, number, window, duration_label, result
from credentials import fingerprint
from rate_limits import rpc_error


def parse_codex(payload):
    primary_set = payload.get('rateLimits')
    mapping = payload.get('rateLimitsByLimitId') or {}
    if not isinstance(primary_set, dict):
        primary_set = mapping.get('codex')
    if not isinstance(primary_set, dict) and len(mapping) == 1:
        primary_set = next(iter(mapping.values()))
    if not isinstance(primary_set, dict): return []
    windows = []
    for key in ('primary', 'secondary'):
        item = primary_set.get(key)
        if not isinstance(item, dict): continue
        minutes = number(item.get('windowDurationMins'))
        windows.append(window(key, duration_label(minutes, '套餐窗口 · ' + key), used_percent=item.get('usedPercent'), reset=item.get('resetsAt'), minutes=minutes))
    return windows

def collect_codex():
    binary = executable('codex')
    if not binary: raise MonitorError('unavailable', '请先安装并登录官方 Codex CLI。')
    process = subprocess.Popen([binary, 'app-server'], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.DEVNULL, bufsize=0, start_new_session=True,
                               cwd=str(SUPPORT if SUPPORT.exists() else HOME))
    with CHILDREN_LOCK: CHILDREN.add(process)
    selector = selectors.DefaultSelector(); selector.register(process.stdout, selectors.EVENT_READ)
    # Cold app-server startup/authentication can exceed 25 seconds on a busy Mac.
    # Remains within the parent collector's 150-second watchdog; no model turn.
    deadline = time.monotonic() + 75
    buffer = b''; received = {}
    def send(value):
        process.stdin.write((json.dumps(value) + '\n').encode()); process.stdin.flush()
    def wait_for(request_id):
        nonlocal buffer
        while request_id not in received:
            if process.poll() is not None: raise MonitorError('auth_required', 'Codex 官方额度服务提前退出，请检查 codex login 状态。')
            left = deadline - time.monotonic()
            if left <= 0:
                stage = {1: '初始化', 2: '账号状态', 3: '额度接口'}[request_id]
                raise MonitorError('network_error', 'Codex ' + stage + '查询超时；未创建模型会话。')
            if not selector.select(timeout=min(left, 1)): continue
            chunk = os.read(process.stdout.fileno(), 65536)
            if not chunk: raise MonitorError('error', 'Codex 官方服务没有返回完整额度响应。')
            buffer += chunk
            if len(buffer) > 2 * 1024 * 1024: raise MonitorError('error', 'Codex 响应超出解析范围。')
            while b'\n' in buffer:
                line, buffer = buffer.split(b'\n', 1)
                try: message = json.loads(line)
                except (ValueError, UnicodeDecodeError): continue
                if isinstance(message, dict) and message.get('id') in (1, 2, 3):
                    received[message['id']] = message
        reply = received[request_id]
        if 'error' in reply:
            raise rpc_error(reply['error'])
        return reply.get('result') or {}
    try:
        send({'id': 1, 'method': 'initialize', 'params': {'clientInfo': {'name': 'monitor', 'title': 'Monitor', 'version': '1.0.0'}, 'capabilities': {'experimentalApi': False}}})
        wait_for(1)
        send({'method': 'initialized', 'params': {}})
        send({'id': 2, 'method': 'account/read', 'params': {'refreshToken': False}})
        account = (wait_for(2).get('account') or {})
        if not account:
            raise MonitorError('auth_required', 'Codex CLI 尚未登录，请运行 codex login。')
        if account.get('type') == 'apiKey':
            return result('codex', 'Codex', '官方 app-server', [], status='unsupported', message='当前是 API Key 登录，不是 ChatGPT Coding Plan；不推算 5 小时或每周额度。')
        send({'id': 3, 'method': 'account/rateLimits/read', 'params': {}})
        payload = wait_for(3)
        windows = parse_codex(payload)
        return result('codex', 'Codex', '官方 CLI · account/rateLimits/read', windows, plan=account.get('planType'),
                      status='ok' if windows else 'unsupported',
                      message='' if windows else '官方未提供可量化的套餐窗口；不以 100% 代替。',
                      note='窗口长度直接采用官方返回值。登录和续期由 Codex CLI 负责。',
                      identity=fingerprint(account.get('email') or account.get('chatgptAccountId') or 'codex'))
    finally:
        selector.close()
        with contextlib.suppress(OSError): process.stdin.close()
        stop_child(process)
