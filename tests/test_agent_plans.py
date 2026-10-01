"""OpenCode Go and ClinePass contracts. Synthetic credentials only; network is disabled."""
import base64
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'collector'))
import extended_plans as E
import monitor
from core import MonitorError
from network import validate_url
from scheduling import GateBook

# Shapes from the vendors' own sources: OpenCode's console route
# packages/console/app/src/routes/zen/go/v1/usage.ts, and the usage-limits
# contract Cline's dashboard client reads ({success, data: {limits: [...]}}).
OPENCODE = {'usage': {
    'rolling': {'status': 'ok', 'percent': 37, 'resetsAt': '2026-10-01T05:00:00.000Z'},
    'weekly': {'status': 'ok', 'percent': 12, 'resetsAt': '2026-10-05T00:00:00.000Z'},
    'monthly': {'status': 'ok', 'percent': 4, 'resetsAt': '2026-10-22T00:00:00.000Z'}}}
CLINE = {'success': True, 'data': {'limits': [
    {'type': 'monthly', 'percentUsed': 53.5, 'resetsAt': '2026-11-01T00:00:00.123456789Z'},
    {'type': 'five_hour', 'percentUsed': 12, 'resetsAt': '2026-10-01T05:00:00Z'},
    {'type': 'weekly', 'percentUsed': 44, 'resetsAt': '2026-10-05T00:00:00Z'}]}}


def jwt(exp):
    enc = lambda x: base64.urlsafe_b64encode(json.dumps(x).encode()).decode().rstrip('=')
    return enc({'alg': 'none'}) + '.' + enc({'exp': exp, 'sub': 'user_synthetic'}) + '.synthetic'


class Home:
    """A disposable home with the vendors' own credential files."""
    def __enter__(self):
        self.folder = tempfile.TemporaryDirectory()
        self.home = Path(self.folder.name)
        self.patches = [patch.object(E, 'HOME', self.home), patch.dict(os.environ, {}, clear=False)]
        for p in self.patches: p.start()
        os.environ.pop('XDG_DATA_HOME', None)
        return self
    def __exit__(self, *exc):
        for p in reversed(self.patches): p.stop()
        self.folder.cleanup()
    def opencode(self, doc):
        path = self.home / '.local/share/opencode/auth.json'
        path.parent.mkdir(parents=True); path.write_text(json.dumps(doc))
    def cline(self, doc):
        path = self.home / '.cline/data/settings/providers.json'
        path.parent.mkdir(parents=True); path.write_text(json.dumps(doc))


def cline_doc(token, account='acct_synthetic', name='cline'):
    return {'version': 1, 'providers': {name: {'settings': {'provider': name, 'auth': {
        'accessToken': token, 'refreshToken': 'refresh-synthetic', 'accountId': account}}}}}


class OpenCodeGoTests(unittest.TestCase):
    def test_used_percent_becomes_remaining(self):
        ws = {w['id']: w for w in E.parse_opencode(OPENCODE)}
        self.assertEqual(ws['opencode-5h']['remainingPercent'], 63)
        self.assertEqual(ws['opencode-5h']['durationMinutes'], 300)
        self.assertEqual(ws['opencode-weekly']['durationMinutes'], 10080)
        self.assertEqual(ws['opencode-monthly']['kind'], 'monthly')
        self.assertIsNone(ws['opencode-monthly']['durationMinutes'])
        self.assertIsNotNone(ws['opencode-5h']['resetAt'])
    def test_rate_limited_window_is_real_zero(self):
        payload = {'usage': {'rolling': {'status': 'rate-limited', 'percent': 100, 'resetsAt': '2026-10-01T05:00:00.000Z'}}}
        self.assertEqual(E.parse_opencode(payload)[0]['remainingPercent'], 0)
    def test_missing_or_invalid_percent_is_not_invented(self):
        for bad in [None, 'x', -1, 101, True]:
            payload = {'usage': {'rolling': {'percent': bad}}}
            self.assertEqual(E.parse_opencode(payload), [], bad)
        with self.assertRaises(MonitorError): E.parse_opencode({'rolling': {}})
    def test_reads_go_key_saved_by_opencode(self):
        with Home() as h:
            h.opencode({'opencode': {'type': 'api', 'key': 'zen-key'}, 'opencode-go': {'type': 'api', 'key': 'go-key'}})
            self.assertEqual(E.opencode_key(), 'go-key')
    def test_falls_back_to_workspace_zen_key(self):
        with Home() as h:
            h.opencode({'opencode': {'type': 'api', 'key': 'zen-key'}})
            self.assertEqual(E.opencode_key(), 'zen-key')
    def test_oauth_entries_and_missing_file_are_not_keys(self):
        with Home() as h:
            with self.assertRaises(MonitorError) as c: E.opencode_key()
            self.assertEqual(c.exception.status, 'auth_required')
            h.opencode({'opencode-go': {'type': 'oauth', 'access': 'x', 'refresh': 'y', 'expires': 1}})
            with self.assertRaises(MonitorError): E.opencode_key()
    def test_xdg_data_home_is_respected(self):
        with Home() as h:
            os.environ['XDG_DATA_HOME'] = str(h.home / 'xdg')
            path = h.home / 'xdg/opencode/auth.json'; path.parent.mkdir(parents=True)
            path.write_text(json.dumps({'opencode-go': {'type': 'api', 'key': 'xdg-key'}}))
            self.assertEqual(E.opencode_key(), 'xdg-key')
    def test_request_uses_bearer_key_only_against_allowlisted_endpoint(self):
        with Home() as h:
            h.opencode({'opencode-go': {'type': 'api', 'key': 'go-key'}})
            with patch.object(E, 'request_json', return_value=OPENCODE) as request:
                value = E.collect_opencode()
            request.assert_called_once_with('https://opencode.ai/zen/go/v1/usage', headers={'Authorization': 'Bearer go-key'})
            self.assertEqual(value['status'], 'ok'); self.assertEqual(len(value['windows']), 3)
            self.assertNotIn('go-key', json.dumps(monitor.public_result(value)))
        validate_url(E.OPENCODE_USAGE)
    def test_no_go_subscription_is_unsupported_not_zero(self):
        with Home() as h:
            h.opencode({'opencode-go': {'type': 'api', 'key': 'go-key'}})
            with patch.object(E, 'request_json', side_effect=MonitorError('permission_required', 'x', http_status=403)):
                with self.assertRaises(MonitorError) as c: E.collect_opencode()
            self.assertEqual(c.exception.status, 'unsupported')
    def test_identity_is_a_digest_of_the_key(self):
        with Home() as h:
            self.assertIsNone(E.opencode_identity())
            h.opencode({'opencode-go': {'type': 'api', 'key': 'go-key'}})
            digest = E.opencode_identity()
            self.assertEqual(len(digest), 64); self.assertNotIn('go-key', digest)


class ClinePassTests(unittest.TestCase):
    def test_windows_ordered_and_used_becomes_remaining(self):
        ws = E.parse_cline(CLINE)
        self.assertEqual([w['id'] for w in ws], ['cline-5h', 'cline-weekly', 'cline-monthly'])
        self.assertEqual(ws[0]['remainingPercent'], 88); self.assertEqual(ws[0]['durationMinutes'], 300)
        self.assertEqual(ws[2]['remainingPercent'], 46.5); self.assertEqual(ws[2]['kind'], 'monthly')
        # Nanosecond timestamps still parse on the system Python 3.9 runtime.
        self.assertIsNotNone(ws[2]['resetAt'])
    def test_unknown_types_and_absent_percent_are_skipped(self):
        payload = {'success': True, 'data': {'limits': [
            {'type': 'daily', 'percentUsed': 10}, {'type': 'weekly'}, {'type': 'five_hour', 'percentUsed': 'x'}, 'junk']}}
        self.assertEqual(E.parse_cline(payload), [])
    def test_broken_envelope_fails_closed(self):
        for payload in [{'success': False, 'data': {'limits': []}}, {'success': True, 'data': {}}, {'limits': []}]:
            with self.assertRaises(MonitorError): E.parse_cline(payload)
    def test_reads_cline_sign_in_and_prefixes_workos(self):
        token = jwt(4_000_000_000)
        with Home() as h:
            h.cline(cline_doc(token))
            with patch.object(E, 'request_json', return_value=CLINE) as request:
                value = E.collect_cline()
            request.assert_called_once_with('https://api.cline.bot/api/v1/users/me/plan/usage-limits',
                                            headers={'Authorization': 'Bearer workos:' + token})
            self.assertEqual(value['status'], 'ok')
            self.assertNotIn(token, json.dumps(monitor.public_result(value)))
        validate_url(E.CLINE_USAGE)
    def test_stored_prefix_is_not_doubled(self):
        token = jwt(4_000_000_000)
        self.assertEqual(E.cline_bearer('workos:' + token), 'workos:' + token)
    def test_legacy_cline_pass_section_is_a_fallback(self):
        with Home() as h:
            h.cline(cline_doc(jwt(4_000_000_000), name='cline-pass'))
            self.assertEqual(E.cline_session()[1], 'acct_synthetic')
    def test_expired_token_is_left_for_cline_to_renew(self):
        with Home() as h:
            h.cline(cline_doc(jwt(1000)))
            with patch.object(E, 'request_json') as request:
                with self.assertRaises(MonitorError) as c: E.collect_cline()
            request.assert_not_called()
            self.assertEqual(c.exception.status, 'unavailable')
    def test_missing_sign_in_requires_login(self):
        with Home() as h:
            with self.assertRaises(MonitorError) as c: E.cline_session()
            self.assertEqual(c.exception.status, 'auth_required')
            h.cline({'version': 1, 'providers': {'cline-pass': {'settings': {'provider': 'cline-pass'}}}})
            with self.assertRaises(MonitorError): E.cline_session()
    def test_no_plan_history_is_unsupported(self):
        with Home() as h:
            h.cline(cline_doc(jwt(4_000_000_000)))
            with patch.object(E, 'request_json', side_effect=MonitorError('error', 'x', http_status=404)):
                with self.assertRaises(MonitorError) as c: E.collect_cline()
            self.assertEqual(c.exception.status, 'unsupported')
            with patch.object(E, 'request_json', return_value={'success': True, 'data': {'limits': []}}):
                self.assertEqual(E.collect_cline()['status'], 'unsupported')
    def test_identity_survives_token_rotation(self):
        with Home() as h:
            h.cline(cline_doc(jwt(4_000_000_000)))
            first = E.cline_identity()
            (h.home / '.cline/data/settings/providers.json').write_text(json.dumps(cline_doc(jwt(4_000_000_001))))
            self.assertEqual(E.cline_identity(), first)
            (h.home / '.cline/data/settings/providers.json').write_text(json.dumps(cline_doc(jwt(4_000_000_001), account='other')))
            self.assertNotEqual(E.cline_identity(), first)


class SchedulingIntegration(unittest.TestCase):
    def test_new_plans_run_through_query_gates(self):
        with tempfile.TemporaryDirectory() as d:
            gates = GateBook(Path(d) / 'gates.json', clock=lambda: 1000, jitter=lambda _: 0)
            fresh = E.checked_result('cline', 'ClinePass', 'fixture', E.parse_cline(CLINE))
            with patch.object(monitor, 'generation', return_value='same'), patch.object(monitor, 'collect_cline', return_value=fresh) as collect:
                value, record = monitor.collect_one('cline', 'cn', None, {}, gates=gates)
                self.assertEqual(value['status'], 'ok'); self.assertEqual(value['pollIntervalSeconds'], 600)
                again, _ = monitor.collect_one('cline', 'cn', value, {'cline': record}, gates=gates)
                collect.assert_called_once()
                self.assertEqual(again['queryStatus'], 'scheduled'); self.assertEqual(again['windows'], value['windows'])
    def test_expired_cline_token_keeps_last_good_reading_as_stale(self):
        with tempfile.TemporaryDirectory() as d:
            clock = [1000]
            gates = GateBook(Path(d) / 'gates.json', clock=lambda: clock[0], jitter=lambda _: 0)
            fresh = E.checked_result('cline', 'ClinePass', 'fixture', E.parse_cline(CLINE))
            with patch.object(monitor, 'generation', return_value='same'):
                with patch.object(monitor, 'collect_cline', return_value=fresh):
                    value, record = monitor.collect_one('cline', 'cn', None, {}, gates=gates)
                clock[0] += 3600
                with patch.object(monitor, 'collect_cline', side_effect=MonitorError('unavailable', 'expired')):
                    later, _ = monitor.collect_one('cline', 'cn', value, {'cline': record}, gates=gates)
            self.assertEqual(later['status'], 'stale'); self.assertEqual(later['windows'], value['windows'])


if __name__ == '__main__':
    unittest.main()
