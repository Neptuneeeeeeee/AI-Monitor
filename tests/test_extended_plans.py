"""Synthetic contract/transport tests. No real accounts or external requests."""
import base64
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch, Mock
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'collector'))
import extended_plans as E
import local_plan_store as S
import monitor
from core import MonitorError, window
from scheduling import GateBook, MIN_INTERVAL
from network import validate_url


def jwt(exp=10000, subject='auth0|synthetic-user'):
    enc = lambda x: base64.urlsafe_b64encode(json.dumps(x).encode()).decode().rstrip('=')
    return enc({'alg': 'none'}) + '.' + enc({'exp': exp, 'sub': subject}) + '.synthetic'


def mini_item(**kw):
    return {'model_name': 'general', 'current_interval_total_count': 1000,
            'current_interval_usage_count': 400, **kw}


class NumericContracts(unittest.TestCase):
    def test_missing_counts_never_invent_quota(self):
        for cap, used, rem in [(None, 3, None), (0, 0, 0), (-1, 0, 0), (10, None, None), (10, -2, None), (10, None, 11)]:
            self.assertIsNone(E.counted('x', 'x', cap, used, rem))
    def test_invalid_explicit_values_fail_closed(self):
        for bad in [True, float('nan'), float('inf'), 'bad']:
            self.assertIsNone(E.counted('x', 'x', 10, used=bad, remaining=5))
    def test_contradictory_counts_rejected(self):
        self.assertIsNone(E.counted('x', 'x', 100, used=70, remaining=90))
    def test_zero_and_full_and_overspend(self):
        for used, remaining in [(0, 100), (100, 0), (120, 0)]:
            self.assertEqual(E.counted('x', 'x', 100, used=used)['remainingPercent'], remaining)
    def test_percent_strict(self):
        for bad in [-1, 101, float('nan'), True, 'text']:
            self.assertIsNone(E.percent(bad))
        self.assertEqual(E.percent('0'), 0)
    def test_labels_cannot_surface_auth_headers(self):
        self.assertIsNone(E.safe_text('Bearer: secret\n'))
        self.assertIsNone(E.safe_text('x' * 100))


class CursorContractTests(unittest.TestCase):
    def payload(self, **kwargs):
        return {'individualUsage': {'plan': {'enabled': True, **kwargs}}, 'billingCycleEnd': '2026-10-01T00:00:00Z'}
    def test_monthly_reported_percent(self):
        w = E.parse_cursor(self.payload(totalPercentUsed=30))[0]
        self.assertEqual(w['remainingPercent'], 70)
        self.assertEqual(w['kind'], 'monthly')
        self.assertIsNone(w['durationMinutes'])
        self.assertIsNotNone(w['resetAt'])
    def test_independent_pools_no_fictional_average(self):
        values = E.parse_cursor(self.payload(autoPercentUsed=10, apiPercentUsed=80))
        self.assertEqual([w['remainingPercent'] for w in values], [90, 20])
        self.assertNotIn('cursor-monthly', [w['id'] for w in values])
    def test_reported_zero_is_valid(self):
        self.assertEqual(E.parse_cursor(self.payload(totalPercentUsed=0))[0]['remainingPercent'], 100)
    def test_real_counts_fallback(self):
        self.assertEqual(E.parse_cursor(self.payload(limit=2000, used=500, remaining=1500))[0]['remainingPercent'], 75)
    def test_missing_not_zero(self):
        for doc in [{}, self.payload(), {'individualUsage': {'plan': {'enabled': False, 'totalPercentUsed': 0}}}]:
            self.assertEqual(E.parse_cursor(doc), [])
    def test_malformed_percent_not_replaced_with_other_guesses(self):
        self.assertEqual(E.parse_cursor(self.payload(totalPercentUsed='bad', limit=100, remaining=90)), [])
    def test_on_demand_team_budget_excluded(self):
        self.assertEqual(E.parse_cursor({'teamUsage': {'onDemand': {'limit': 100}}, 'individualUsage': {'onDemand': {'remaining': 100}}}), [])
    def test_cookie_format_and_expiration(self):
        token = jwt()
        self.assertEqual(E.cursor_cookie(token, now=100), 'WorkosCursorSessionToken=synthetic-user%3A%3A' + token)
        for token in [jwt(exp=150), jwt(subject='bad;Cookie=oops'), 'a.b.c', 'bad\r\nCookie: x']:
            with self.assertRaises(MonitorError): E.cursor_cookie(token, now=100)
    def test_only_expected_endpoint(self):
        with patch.object(E, 'read_app_value', return_value=(jwt(exp=9999999999), 100)), patch.object(E, 'request_json', return_value=self.payload(totalPercentUsed=20)) as request:
            value = E.collect_cursor()
            self.assertEqual(value['status'], 'ok')
            self.assertEqual(request.call_args.args, ('https://cursor.com/api/usage-summary',))
            self.assertNotIn('synthetic-user', json.dumps(value))
    def test_missing_login_no_network(self):
        with patch.object(E, 'read_app_value', return_value=(None, 100)), patch.object(E, 'request_json') as request:
            with self.assertRaises(MonitorError): E.collect_cursor()
            request.assert_not_called()


class MiniMaxContractTests(unittest.TestCase):
    def test_usage_count_is_remaining(self):
        w = E.parse_minimax({'model_remains': [mini_item()]})[0]
        self.assertEqual(w['remainingPercent'], 40)
        self.assertEqual(w['remaining'], 400)
    def test_wrapped_model_remains(self):
        self.assertEqual(E.parse_minimax({'data': {'model_remains': [mini_item()]}})[0]['remainingPercent'], 40)
    def test_percent_authoritative_even_zero_placeholder_counts(self):
        w = E.parse_minimax({'model_remains': [mini_item(current_interval_total_count=0, current_interval_usage_count=0, current_interval_remaining_percent=72)]})[0]
        self.assertEqual(w['remainingPercent'], 72)
        self.assertIsNone(w['limit'])
    def test_real_exhaustion_is_zero(self):
        self.assertEqual(E.parse_minimax({'model_remains': [mini_item(current_interval_usage_count=0)]})[0]['remainingPercent'], 0)
    def test_unavailable_lane_not_full(self):
        self.assertEqual(E.parse_minimax({'model_remains': [mini_item(current_interval_status=3, current_interval_remaining_percent=100)]}), [])
    def test_missing_count_not_zero(self):
        self.assertEqual(E.parse_minimax({'model_remains': [{'model_name': 'general', 'remains_time': 120000}]}), [])
    def test_remains_time_is_not_tokens(self):
        w = E.parse_minimax({'model_remains': [mini_item(remains_time=999999999)]})[0]
        self.assertEqual(w['remaining'], 400)
        self.assertIsNone(w['resetAt'])
    def test_unified_pool_not_counted_per_model(self):
        ws = E.parse_minimax({'model_remains': [mini_item(), mini_item(model_name='MiniMax-M3')]})
        self.assertEqual(len(ws), 1)
    def test_other_modalities_not_coding_quota(self):
        self.assertEqual(E.parse_minimax({'model_remains': [mini_item(model_name='speech-02')]}), [])
    def test_explicit_week_and_millisecond_reset(self):
        w = E.parse_minimax({'model_remains': [mini_item(start_time=1800000000000, end_time=1800018000000, current_weekly_total_count=2000, current_weekly_usage_count=1800, weekly_end_time=1800604800000)]})
        self.assertEqual([x['durationMinutes'] for x in w], [300, 10080])
        self.assertEqual(w[1]['remainingPercent'], 90)
        self.assertEqual(w[0]['resetAt'], 1800018000)
    def test_denied_and_no_plan_have_no_amount(self):
        for code in [1004, 2062]:
            with self.assertRaises(MonitorError) as c: E.parse_minimax({'base_resp': {'status_code': code}, 'model_remains': [mini_item()]})
            self.assertEqual(c.exception.status, 'auth_required')
    def test_unknown_provider_error_not_ok(self):
        with self.assertRaises(MonitorError): E.parse_minimax({'base_resp': {'status_code': 9999}})
    def test_legacy_service_usage_is_used(self):
        w = E.parse_minimax({'services': [{'service_type': 'text_generation', 'window_type': '5 hours', 'usage': 20, 'limit': 100, 'percent': 20}]})
        self.assertEqual(w[0]['remainingPercent'], 80)
    def test_legacy_contradictory_percent_rejected(self):
        self.assertEqual(E.parse_minimax({'services': [{'service_type': 'text_generation', 'window_type': '5 hours', 'usage': 20, 'limit': 100, 'percent': 80}]}), [])
    def test_regions_not_retried(self):
        for region, host in [('cn', 'www.minimaxi.com'), ('global', 'www.minimax.io')]:
            with patch.object(E, 'minimax_settings', return_value={'minimaxRegion': region}), patch.object(E, 'own_key', return_value='synthetic-key') as key, patch.object(E, 'request_json', side_effect=MonitorError('auth_required', 'fixture')) as req:
                with self.assertRaises(MonitorError): E.collect_minimax()
                key.assert_called_once_with('minimax-' + region)
                self.assertEqual(req.call_count, 1)
                self.assertEqual(req.call_args.args[0], 'https://' + host + '/v1/token_plan/remains')
    def test_invalid_settings_stops_before_key_read(self):
        with patch.object(E, 'read_json', return_value={'minimaxRegion': 'other'}), patch.object(E, 'own_key') as key:
            with self.assertRaises(MonitorError): E.collect_minimax()
            key.assert_not_called()
    def test_missing_key_no_request(self):
        with patch.object(E, 'minimax_settings', return_value={}), patch.object(E, 'own_key', return_value=None), patch.object(E, 'request_json') as req:
            with self.assertRaises(MonitorError): E.collect_minimax()
            req.assert_not_called()
    def test_invalid_count_and_invalid_percent_rejected(self):
        self.assertEqual(E.parse_minimax({'model_remains': [mini_item(current_interval_usage_count=-1)]}), [])
        self.assertEqual(E.parse_minimax({'model_remains': [mini_item(current_interval_remaining_percent=101)]}), [])


class WindsurfContractTests(unittest.TestCase):
    def test_cached_daily_weekly_only(self):
        ws = E.parse_windsurf({'quotaUsage': {'dailyRemainingPercent': 80, 'weeklyRemainingPercent': 25, 'dailyResetAtUnix': 1800000000}})
        self.assertEqual([w['remainingPercent'] for w in ws], [80, 25])
        self.assertEqual([w['durationMinutes'] for w in ws], [1440, 10080])
    def test_legacy_usage_not_estimated_from_subscription_name(self):
        ws = E.parse_windsurf({'usage': {'messages': 100, 'usedMessages': 10, 'flowActions': 50, 'remainingFlowActions': 15}})
        self.assertEqual([w['remainingPercent'] for w in ws], [90, 30])
        self.assertEqual(E.parse_windsurf({'planName': 'Pro'}), [])
    def test_cached_not_fresh_and_original_file_time(self):
        data = {'quotaUsage': {'dailyRemainingPercent': 0}, 'planName': 'Pro'}
        with patch.object(E, 'read_app_value', return_value=(json.dumps(data), 1000)), patch.object(E, 'request_json') as req:
            value = E.collect_windsurf()
            self.assertEqual(value['fetchedAt'], 1000)
            self.assertEqual(value['status'], 'stale')
            self.assertIn('文件修改时间', value['note'])
            req.assert_not_called()
    def test_malformed_never_connected(self):
        for val in ['[]', 'bad']:
            with patch.object(E, 'read_app_value', return_value=(val, 100)):
                with self.assertRaises(MonitorError): E.collect_windsurf()
    def test_invalid_percent_excluded(self):
        self.assertEqual(E.parse_windsurf({'quotaUsage': {'dailyRemainingPercent': -5, 'weeklyRemainingPercent': float('nan')}}), [])


class KiroContractTests(unittest.TestCase):
    def test_real_counter_and_no_false_reset(self):
        v = E.parse_kiro('KIRO PRO\nMonthly credits:\n████ 10% (resets on 01/01)\n(10.00 of 100 covered in plan)\nBonus credits: 7/99 credits used')
        self.assertEqual(v['windows'][0]['remainingPercent'], 90)
        self.assertIsNone(v['windows'][0]['resetAt'])
        self.assertEqual(len(v['windows']), 1)
    def test_plan_only_no_free_tier_guess(self):
        for text in ['Plan: KIRO PRO MAX | 1 usage breakdowns', 'KIRO FREE\nMonthly credits: 100%', 'Bonus credits: 0/100 credits used']:
            self.assertEqual(E.parse_kiro(text)['windows'], [])
    def test_estimated_is_not_final_bill(self):
        v = E.parse_kiro('Estimated Usage\n(25 of 100 covered in plan)')
        self.assertEqual(v['status'], 'partial')
        self.assertIn('估计', v['message'])
    def test_ansi_and_decimal_counts(self):
        v = E.parse_kiro('\x1b[32m(1,250.50 of 5,000 covered in plan)\x1b[0m')
        self.assertAlmostEqual(v['windows'][0]['remainingPercent'], 74.99)
    def test_zero_cap_unsupported(self):
        self.assertEqual(E.parse_kiro('(0 of 0 covered in plan)')['windows'], [])
    def test_auth_error_is_actionable(self):
        with self.assertRaises(MonitorError) as c: E.parse_kiro('Not logged in')
        self.assertEqual(c.exception.status, 'auth_required')
    def test_exact_usage_command_no_inference_fallback(self):
        with patch.object(E, 'executable', return_value='/fixture/kiro-cli'), patch.object(E, 'run', return_value=(0, b'(25 of 100 covered in plan)')) as command:
            v = E.collect_kiro()
            command.assert_called_once_with(['/fixture/kiro-cli', 'chat', '--no-interactive', '/usage'], timeout=25)
            self.assertEqual(v['windows'][0]['remainingPercent'], 75)
    def test_nonzero_exit_rejected_even_valid_counter(self):
        with patch.object(E, 'executable', return_value='/fixture/kiro-cli'), patch.object(E, 'run', return_value=(1, b'(25 of 100 covered in plan)')):
            with self.assertRaises(MonitorError): E.collect_kiro()
    def test_missing_cli_no_spawn(self):
        with patch.object(E, 'executable', return_value=None), patch.object(E, 'run') as cmd:
            with self.assertRaises(MonitorError): E.collect_kiro()
            cmd.assert_not_called()


class LocalStateTests(unittest.TestCase):
    def create(self, directory, value='synthetic', wal=False):
        db = Path(directory) / 'state.vscdb'
        connection = sqlite3.connect(db)
        if wal:
            connection.execute('PRAGMA journal_mode=WAL')
        connection.execute('CREATE TABLE ItemTable (key TEXT PRIMARY KEY, value BLOB)')
        connection.execute('INSERT INTO ItemTable VALUES (?, ?)', ('cursorAuth/accessToken', value))
        connection.commit()
        return db, connection
    def hashes(self, db):
        return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in db.parent.iterdir() if p.is_file()}
    def test_no_source_changes(self):
        with tempfile.TemporaryDirectory() as d:
            db, c = self.create(d); c.close(); old = self.hashes(db)
            self.assertEqual(S.read_app_value(db, 'cursorAuth/accessToken')[0], 'synthetic')
            self.assertEqual(self.hashes(db), old)
    def test_active_wal_snapshot(self):
        with tempfile.TemporaryDirectory() as d:
            db, c = self.create(d, 'wal-value', True)
            try:
                old = self.hashes(db)
                self.assertEqual(S.read_app_value(db, 'cursorAuth/accessToken')[0], 'wal-value')
                self.assertEqual(self.hashes(db), old)
            finally: c.close()
    def test_utf16_le_value(self):
        with tempfile.TemporaryDirectory() as d:
            db, c = self.create(d, 'encoded-token'.encode('utf-16-le')); c.close()
            self.assertEqual(S.read_app_value(db, 'cursorAuth/accessToken')[0], 'encoded-token')
    def test_unrelated_key_never_read(self):
        with self.assertRaises(MonitorError): S.read_app_value('/fixture/no-db', 'chat.history')
    def test_missing_key_is_none(self):
        with tempfile.TemporaryDirectory() as d:
            db, c = self.create(d); c.close()
            self.assertIsNone(S.read_app_value(db, 'windsurf.settings.cachedPlanInfo')[0])
    def test_size_limit(self):
        with tempfile.TemporaryDirectory() as d:
            db, c = self.create(d); c.close()
            with patch.object(S, 'MAX_DATABASE_BYTES', 1):
                with self.assertRaises(MonitorError): S.read_app_value(db, 'cursorAuth/accessToken')
    def test_invalid_bytes_not_forwarded(self):
        with tempfile.TemporaryDirectory() as d:
            db, c = self.create(d, b'\xff\xff\x00'); c.close()
            with self.assertRaises(MonitorError): S.read_app_value(db, 'cursorAuth/accessToken')


class IntegrationGuards(unittest.TestCase):
    def test_registries_agree(self):
        self.assertEqual(set(MIN_INTERVAL), set(monitor.NAMES))
        self.assertEqual(len(monitor.NAMES), 10)
        swift = (ROOT/'Sources/MonitorCore/Models.swift').read_text()
        for name in monitor.NAMES: self.assertIn('ProviderInfo(id: "' + name + '"', swift)
    def test_removed_key_cards_not_removed_providers(self):
        source = (ROOT/'Sources/MonitorShared/SettingsPanel.swift').read_text()
        self.assertNotIn('SettingsGroup("Kimi Code")', source)
        self.assertNotIn('SettingsGroup("GLM Coding Plan")', source)
        self.assertNotIn('kimiKey', source)
        self.assertNotIn('glmKey', source)
        self.assertIn('kimi', monitor.NAMES); self.assertIn('glm', monitor.NAMES)
    def test_no_default_new_accounts(self):
        self.assertEqual(json.loads((ROOT/'Config/profile.json').read_text())['defaultEnabledProviders'], [])
    def test_allowlisted_hosts_only(self):
        for url in ['https://cursor.com/api/usage-summary', *E.MINIMAX_ENDPOINTS.values()]: validate_url(url)
        for url in ['https://evil.example/v1/token_plan/remains', 'https://www.minimaxi.com/v1/token_plan/remains?key=x', 'http://cursor.com/api/usage-summary']:
            with self.assertRaises(MonitorError): validate_url(url)
    def test_changed_context_suppresses_old_account_cache(self):
        with tempfile.TemporaryDirectory() as d:
            gates = GateBook(Path(d)/'gates.json', clock=lambda: 1000, jitter=lambda _:0)
            old = E.checked_result('cursor', 'Cursor', 'fixture', [window('cursor-monthly', 'month', remaining_percent=77)])
            gates.reserve('cursor')
            with patch.object(monitor, 'generation', return_value='new'), patch.object(monitor, 'collect_cursor') as collect:
                value, _ = monitor.collect_one('cursor', 'cn', old, {'cursor': {'lastGood': old, 'generation': 'old'}}, gates=gates)
                self.assertEqual(value['windows'], [])
                collect.assert_not_called()
    def test_generation_change_during_read_is_not_success(self):
        with tempfile.TemporaryDirectory() as d:
            gates = GateBook(Path(d)/'gates.json', clock=lambda: 1000, jitter=lambda _:0)
            fresh = E.checked_result('cursor', 'Cursor', 'fixture', [window('cursor-monthly', 'month', remaining_percent=77)])
            with patch.object(monitor, 'generation', side_effect=['one','two']), patch.object(monitor, 'collect_cursor', return_value=fresh):
                value, record = monitor.collect_one('cursor', 'cn', None, {}, gates=gates)
                self.assertEqual(value['windows'], [])
                self.assertTrue(record['authBlocked'])
    def test_no_added_broad_system_permissions(self):
        import plistlib
        self.assertEqual(plistlib.loads((ROOT/'Config/Entitlements.plist').read_bytes()), {})
