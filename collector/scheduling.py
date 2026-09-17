"""Persistent provider-wide query gates, independent of credential/cache changes.

These conservative floors are Monitor design choices, not provider-advertised limits.
Manual refresh, restarts, toggling a provider, and --no-cache use the same gates.
A request lease is fsynced BEFORE spawning a CLI or making a request, so killing the
collector cannot turn a reconnect/relaunch loop into a polling storm.
"""
import random
import threading
import time
from pathlib import Path
from core import atomic_json, read_json, number

MIN_INTERVAL = {'claude': 600, 'kimi': 300, 'codex': 300, 'glm': 300, 'copilot': 600, 'antigravity': 300}
POLICY_VERSION = 1


def interval_for(pid, requested=300):
    return max(MIN_INTERVAL[pid], min(86400, max(300, number(requested) or 300)))


def backoff_seconds(error, failures):
    # Retry-After may exceed our locally computed cap; never shorten it.
    if error.status == 'rate_limited':
        base = min(7200, 900 * 2 ** min(8, max(0, failures - 1)))
    elif error.status in ('auth_required', 'permission_required', 'unsupported'):
        base = 900
    else:
        base = min(3600, 300 * 2 ** min(4, max(0, failures - 1)))
    return max(base, max(0, number(error.retry_after) or 0))


class GateBook:
    def __init__(self, path, *, legacy=None, previous=None, clock=time.time, jitter=None):
        self.path = Path(path)
        self.clock = clock
        self.jitter = jitter or (lambda delay: random.uniform(0, min(60, delay * 0.05)))
        self.lock = threading.Lock()
        doc = read_json(self.path, {})
        self.providers = dict(doc.get('providers', {})) if isinstance(doc, dict) and doc.get('version') == POLICY_VERSION else {}
        legacy, previous = legacy or {}, previous or {}
        changed = False
        for pid in MIN_INTERVAL:
            if pid in self.providers: continue
            old = legacy.get(pid) or {}
            cached = previous.get(pid) or {}
            attempt = number(old.get('lastAttempt')) or number(cached.get('fetchedAt')) or number(cached.get('attemptedAt')) or 0
            if not old and not cached: continue
            status = old.get('status') or cached.get('status', 'ok')
            next_at = max(number(old.get('nextAttempt')) or 0, attempt + MIN_INTERVAL[pid])
            if status == 'rate_limited':
                # Existing versions used tiny waits and a token-dependent gate. Give
                # an already limited service a genuine quiet interval on upgrade.
                next_at = max(next_at, self.clock() + 900)
            self.providers[pid] = {
                'lastAttempt': attempt, 'nextAttempt': next_at, 'status': status,
                'reason': 'cooldown' if status not in ('ok', 'partial') else 'interval',
                'failures': min(10, int(old.get('failures', 0))),
                'rateFailures': min(10, int(old.get('failures', 1))) if status == 'rate_limited' else 0,
                'requestCount': 0, 'migratedAt': self.clock(),
            }
            changed = True
        if changed: self._save()

    def _save(self):
        atomic_json(self.path, {'version': POLICY_VERSION, 'providers': self.providers})

    def get(self, pid):
        with self.lock: return dict(self.providers.get(pid) or {})

    def reserve(self, pid, requested=300):
        """Return (allowed, immutable gate). force intentionally does not exist."""
        with self.lock:
            record = dict(self.providers.get(pid) or {})
            if number(record.get('lastAttempt')):
                extended = max(number(record.get('nextAttempt')) or 0,
                               record['lastAttempt'] + interval_for(pid, requested))
                if extended > (number(record.get('nextAttempt')) or 0):
                    record['nextAttempt'] = extended
                    self.providers[pid] = record
                    self._save()
            if (number(record.get('nextAttempt')) or 0) > self.clock():
                return False, record
            now = self.clock()
            record.update({'lastAttempt': now, 'nextAttempt': now + interval_for(pid, requested),
                           'reason': 'in_flight', 'requestCount': int(record.get('requestCount', 0)) + 1})
            self.providers[pid] = record
            self._save()
            return True, dict(record)

    def success(self, pid, requested=300):
        with self.lock:
            record = dict(self.providers.get(pid) or {})
            previous_limits = int(record.get('rateFailures', 0))
            interval = interval_for(pid, requested)
            if previous_limits:
                # Recover gradually instead of returning immediately to fast polling.
                # The ramp is a multiple of this provider's own interval, so it converges
                # back to that interval instead of an unrelated constant. The hard cooldown
                # applied after each real rate limit lives in failure()/backoff_seconds.
                interval = max(interval, min(7200, interval * 2 ** min(3, previous_limits - 1)))
            record.update({'lastFinished': self.clock(), 'nextAttempt': self.clock() + interval + self.jitter(interval),
                           'status': 'ok', 'reason': 'interval', 'failures': 0,
                           'rateFailures': max(0, previous_limits - 1), 'intervalSeconds': interval})
            self.providers[pid] = record; self._save()
            return dict(record)

    def failure(self, pid, error, requested=300):
        with self.lock:
            record = dict(self.providers.get(pid) or {})
            failures = min(20, int(record.get('failures', 0)) + 1)
            limits = min(20, int(record.get('rateFailures', 0)) + (1 if error.status == 'rate_limited' else 0))
            delay = max(interval_for(pid, requested), backoff_seconds(error, limits if error.status == 'rate_limited' else failures))
            record.update({'lastFinished': self.clock(), 'nextAttempt': self.clock() + delay + self.jitter(delay),
                           'status': error.status, 'reason': 'cooldown', 'failures': failures,
                           'rateFailures': limits, 'intervalSeconds': interval_for(pid, requested),
                           'httpStatus': error.http_status})
            self.providers[pid] = record; self._save()
            return dict(record)
