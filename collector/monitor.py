#!/usr/bin/env python3
"""One bounded collection round. stdout is exclusively the redacted UI snapshot."""
from concurrent.futures import ThreadPoolExecutor, as_completed
import argparse
import contextlib
import fcntl
import hashlib
import json
import os
from pathlib import Path
import signal
import sys
import time
from core import HOME, SUPPORT, MonitorError, read_json, atomic_json, CHILDREN, CHILDREN_LOCK, stop_child, run
from kimi_provider import collect_kimi, kimi_home
from codex_provider import collect_codex
from other_providers import collect_claude, collect_glm, collect_copilot
from antigravity_provider import collect_antigravity, official_processes
from extended_plans import collect_cursor, collect_minimax, collect_windsurf, collect_kiro, DB_PATHS, NEW_IDS
from scheduling import GateBook, interval_for
from rate_limits import RATE_MESSAGE
from last_good import choose, historical, update_record, TRANSIENT, measured

NAMES = {'kimi': 'Kimi Code', 'codex': 'Codex', 'claude': 'Claude Code', 'glm': 'GLM Coding Plan', 'copilot': 'GitHub Copilot', 'antigravity': 'Antigravity', 'cursor': 'Cursor', 'minimax': 'MiniMax', 'windsurf': 'Windsurf', 'kiro': 'Kiro'}
PUBLIC_KEYS = {'id', 'name', 'status', 'source', 'message', 'plan', 'fetchedAt', 'attemptedAt', 'windows', 'note', 'nextQueryAt', 'pollIntervalSeconds', 'queryStatus', 'liveStatus', 'historical'}


def generation(pid, region):
    # File metadata is a conservative cache-invalidation guard, not proof of identity.
    # Unknown or local Antigravity identity: never reuse a failed fetch as current data.
    if pid == 'antigravity':
        # Cache invalidation by same-user official process; never inspect argv.
        rc, out = run(['/bin/ps', '-U', str(os.getuid()), '-ww', '-o', 'pid=,comm='], timeout=4)
        processes = official_processes(out.decode('utf-8', 'replace')) if rc == 0 else []
        return hashlib.sha256(json.dumps(processes).encode()).hexdigest() if processes else None
    paths = {
        'kimi': [kimi_home() / 'credentials/kimi-code.json', kimi_home() / 'config.toml'],
        'codex': [Path(os.environ.get('CODEX_HOME', str(HOME / '.codex'))) / 'auth.json'],
        'claude': [HOME / '.claude/.credentials.json'],
        'copilot': [HOME / '.config/gh/hosts.yml'],
        'glm': [], 'antigravity': [],
        'cursor': [HOME / DB_PATHS['cursor'], Path(str(HOME / DB_PATHS['cursor']) + '-wal')],
        'windsurf': [HOME / DB_PATHS['windsurf'], Path(str(HOME / DB_PATHS['windsurf']) + '-wal')],
        'minimax': [SUPPORT / 'plan-connections.json'],
        'kiro': [],
    }[pid]
    # Unrelated Keychain writes must not invalidate quota observations.
    if pid == 'glm':
        paths += [SUPPORT / 'glm-account-generation.json']
    values = []
    for path in paths:
        try:
            st = path.stat(); values.append((str(path), st.st_ino, st.st_size, st.st_mtime_ns))
        except OSError: pass
    if not values: return None
    return hashlib.sha256(json.dumps([pid, region, values]).encode()).hexdigest()

def public_result(value):
    return {key: value.get(key) for key in PUBLIC_KEYS if key in value}

def error_result(pid, error, old=None, same_generation=False):
    value = {'id': pid, 'name': NAMES[pid], 'status': error.status, 'source': error.source,
             'message': error.message, 'plan': None, 'fetchedAt': None, 'attemptedAt': time.time(), 'windows': [], 'note': None}
    if error.status in TRANSIENT and measured(old):
        value = historical(old, error.status, error.message, same_generation)

    return value

def with_schedule(value, record, pid, requested, query_status):
    value = public_result(value)
    value['nextQueryAt'] = record.get('nextAttempt')
    value['pollIntervalSeconds'] = record.get('intervalSeconds') or interval_for(pid, requested)
    value['queryStatus'] = query_status
    return value


def collect_one(pid, region, previous, state, force=False, *, gates, requested=300):
    try: before = generation(pid, region)
    except MonitorError: before = None
    record = state.get(pid) or {}
    saved = choose(record, previous) if record.get('region', region) == region and not record.get('authBlocked') else None
    same = before is not None and record.get('generation') == before and record.get('region', region) == region
    # Do not carry new-provider results across an unknown/changed account context.
    # Kiro has no local identity proof, so transient failures omit its cached balance.
    if pid in NEW_IDS and not same:
        saved = None
        record = {}
    # Reserve/persist the gate BEFORE touching credentials or spawning an adapter.
    # --force means check which sources are due, not bypass their protection.
    allowed, gate = gates.reserve(pid, requested)
    if not allowed:
        if gate.get('reason') == 'cooldown':
            status = gate.get('status') or 'network_error'
            message = RATE_MESSAGE if status == 'rate_limited' else (record.get('message') or '已暂停查询，等待下次检查。')
            if pid == 'claude' and status in ('permission_required', 'unavailable'):
                confirmation = read_json(SUPPORT/'claude-authorization.json', {})
                if confirmation.get('authorizedAt', 0) > gate.get('lastFinished', gate.get('lastAttempt', 0)):
                    status = 'unavailable'
                    message = '固定组件授权已验证；等待现有查询保护窗口结束。'
            value = error_result(pid, MonitorError(status, message), saved, same)
            query_status = 'cooldown'
        elif saved:
            value = dict(saved) if same and gate.get('status') in ('ok', 'partial') else historical(saved, gate.get('status', 'unavailable'), '使用上次成功读数，等待计划中的刷新。', same)
            query_status = 'scheduled'
        else:
            value = error_result(pid, MonitorError('unavailable', '已安排下次查询；当前没有已验证的可用缓存。'))
            query_status = 'scheduled'
        # Cache checks are not new request attempts and do not renew fetchedAt.
        value['attemptedAt'] = gate.get('lastAttempt') or (saved or {}).get('attemptedAt')
        return with_schedule(value, gate, pid, requested, query_status), record
    functions = {'kimi': collect_kimi, 'codex': collect_codex, 'claude': collect_claude,
                 'glm': lambda: collect_glm(region), 'copilot': collect_copilot, 'antigravity': collect_antigravity,
                 'cursor': collect_cursor, 'minimax': collect_minimax, 'windsurf': collect_windsurf, 'kiro': collect_kiro}
    try:
        value = public_result(functions[pid]())
        updated = gates.success(pid, requested)
        value['attemptedAt'] = gate['lastAttempt']
        value = with_schedule(value, updated, pid, requested, 'updated')
        try: after = generation(pid, region)
        except MonitorError: after = None
        if pid in NEW_IDS and before is not None and before != after:
            value = error_result(pid, MonitorError('unavailable', '查询期间账号状态发生变化；未保存可能属于旧账号的额度。'))
            value = with_schedule(value, updated, pid, requested, 'scheduled')
            return value, {'generation': after, 'region': region, 'authBlocked': True, 'status': 'unavailable'}
        return value, update_record(record, value, generation=after, region=region, success=True)
    except MonitorError as error: pass_error = error
    except Exception as error:
        pass_error = MonitorError('error', '本地适配器遇到 ' + type(error).__name__ + '，已暂停查询。')
    updated = gates.failure(pid, pass_error, requested)
    try: after = generation(pid, region)
    except MonitorError: after = None
    value = error_result(pid, pass_error, saved, same and after == before)
    value['attemptedAt'] = gate['lastAttempt']
    value = with_schedule(value, updated, pid, requested, 'cooldown')
    base = dict(record)
    if saved and not base.get('lastGood'): base['lastGood'] = saved
    return value, update_record(base, value, generation=after, region=region, error_status=pass_error.status)


def shutdown(signum, frame):
    with CHILDREN_LOCK: children = list(CHILDREN)
    for child in children: stop_child(child)
    # The parent owns this one-shot collector. Network requests have their own deadlines.
    os._exit(128 + signum)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--providers', required=True, help='Explicit comma-separated provider selection.')
    parser.add_argument('--glm-region', choices=('cn', 'global'), default='cn')
    parser.add_argument('--force', action='store_true', help='Check due sources; never bypass query protection.')
    parser.add_argument('--interval-seconds', type=int, default=300)
    parser.add_argument('--no-cache', action='store_true', help='Skip quota cache only; persistent request gates are ALWAYS enforced.')
    args = parser.parse_args()
    selected = list(dict.fromkeys(x.strip() for x in args.providers.split(',') if x.strip()))
    if not selected or any(pid not in NAMES for pid in selected): parser.error('Unknown or empty provider selection')
    SUPPORT.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(SUPPORT, 0o700)
    lock_file = open(SUPPORT / 'collection.lock', 'a')
    os.chmod(SUPPORT / 'collection.lock', 0o600)
    try: fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print('Collection already running.', file=sys.stderr); return 75
    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGALRM, shutdown)
    signal.alarm(150)
    old = read_json(SUPPORT / 'snapshot.json', {})
    previous = {p['id']: p for p in old.get('providers', []) if isinstance(p, dict) and p.get('id') in NAMES}
    state = read_json(SUPPORT / 'provider-state.json', {})
    if not isinstance(state, dict): state = {}
    gates = GateBook(SUPPORT / 'request-gates.json', legacy=state, previous=previous)
    results, states = {}, dict(state)  # Disabled providers keep their cooldown/cache records.
    try:
        with ThreadPoolExecutor(max_workers=2, thread_name_prefix='quota') as pool:
            futures = {pool.submit(collect_one, pid, args.glm_region,
                                   None if args.no_cache else previous.get(pid),
                                   {} if args.no_cache else state, args.force,
                                   gates=gates, requested=args.interval_seconds): pid for pid in selected}
            for future in as_completed(futures):
                pid = futures[future]
                results[pid], record = future.result()
                if record and not args.no_cache:
                    states[pid] = record
                    # Persist each completed provider, not only the slowest batch's finish.
                    atomic_json(SUPPORT / 'provider-state.json', states)
        snapshot = {'schemaVersion': 1, 'generatedAt': time.time(), 'providers': [results[pid] for pid in selected]}
        if not args.no_cache:
            atomic_json(SUPPORT / 'snapshot.json', snapshot)
            atomic_json(SUPPORT / 'provider-state.json', states)
        print(json.dumps(snapshot, ensure_ascii=False, allow_nan=False, separators=(',', ':')))
        return 0
    finally:
        signal.alarm(0)
        fcntl.flock(lock_file, fcntl.LOCK_UN); lock_file.close()

if __name__ == '__main__':
    raise SystemExit(main())
