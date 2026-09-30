"""Offline cache and authorization regressions. Values are synthetic fixtures."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'collector'))
from core import MonitorError, window
from last_good import choose, historical, update_record
from monitor import collect_one, error_result
from scheduling import GateBook
from credentials import keychain


def good():
    return {'id':'kimi','name':'Kimi','status':'ok','source':'test fixture', 'message':'', 'fetchedAt':1000, 'windows':[window('short','Session',remaining_percent=73,minutes=300)]}

class LastValueTests(unittest.TestCase):
    def test_unavailable_uses_last_good(self):
        value=error_result('kimi',MonitorError('unavailable','wait'),good(),False)
        self.assertEqual(value['windows'][0]['remainingPercent'],73);self.assertEqual(value['status'],'stale')
        self.assertEqual(value['fetchedAt'],1000);self.assertTrue(value['historical'])
    def test_local_authorization_error_keeps_historical_value(self):
        value=error_result('kimi',MonitorError('permission_required','local'),good(),False)
        self.assertEqual(value['windows'][0]['remainingPercent'],73);self.assertEqual(value['liveStatus'],'permission_required')
    def test_confirmed_login_rejection_does_not_reuse(self):
        self.assertEqual(error_result('kimi',MonitorError('auth_required','401'),good(),True)['windows'],[])
    def test_no_success_never_invents_value(self):
        self.assertEqual(error_result('kimi',MonitorError('unavailable','wait'),None,True)['windows'],[])
    def test_error_cannot_overwrite_last_good(self):
        old={'lastGood':good()}
        updated=update_record(old,{'id':'kimi','status':'error','windows':[]},error_status='error')
        self.assertEqual(updated['lastGood'],good())
    def test_latest_success_wins(self):
        newer=good();newer['fetchedAt']=2000
        updated=update_record({'lastGood':good()},newer,success=True)
        self.assertEqual(updated['lastGood']['fetchedAt'],2000)
    def test_repeated_stale_does_not_advance_time(self):
        value=good()
        for _ in range(30):value=historical(value,'rate_limited','wait',True)
        self.assertEqual(value['fetchedAt'],1000);self.assertEqual(value['windows'][0]['remainingPercent'],73)
    def test_known_unsupported_account_blocks_old_values(self):
        record=update_record({'lastGood':good()},{'status':'unsupported','windows':[]},success=True)
        self.assertTrue(record['authBlocked'])
    def test_same_value_does_not_get_mutated_by_caller(self):
        old=good();value=historical(old,'unavailable','wait');value['windows'][0]['remainingPercent']=0
        self.assertEqual(old['windows'][0]['remainingPercent'],73)
    def test_metadata_change_keeps_stale_on_scheduled_path(self):
        with tempfile.TemporaryDirectory() as path:
            gates=GateBook(Path(path)/'gates.json',clock=lambda:2000,jitter=lambda _:0)
            gates.reserve('kimi');gates.success('kimi')
            state={'kimi':{'generation':'old','region':'cn','lastGood':good()}}
            with patch('monitor.generation',return_value='new'),patch('monitor.collect_kimi') as fn:
                value,_=collect_one('kimi','cn',None,state,True,gates=gates)
            fn.assert_not_called();self.assertEqual(value['status'],'stale');self.assertEqual(value['fetchedAt'],1000)
    def test_region_change_does_not_reuse(self):
        with tempfile.TemporaryDirectory() as path:
            gates=GateBook(Path(path)/'gates.json',clock=lambda:2000,jitter=lambda _:0);gates.reserve('glm')
            state={'glm':{'generation':'x','region':'cn','lastGood':good()}}
            with patch('monitor.generation',return_value='x'):
                value,_=collect_one('glm','global',None,state,gates=gates)
            self.assertEqual(value['windows'],[])

class ClaudeCooldownTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name)
        self.now = 2000
        self.good = {**good(), 'id': 'claude', 'name': 'Claude'}
        self.record = {'generation': 'same', 'region': 'cn', 'authBlocked': True,
                       'status': 'auth_required', 'lastGood': self.good}

    def tearDown(self):
        self.tmp.cleanup()

    def book(self, name='gates'):
        return GateBook(self.path / (name + '.json'), clock=lambda: self.now, jitter=lambda _: 0)

    def test_transient_failure_after_login_error_keeps_history_through_restart(self):
        for status in ['rate_limited', 'network_error', 'unavailable', 'permission_required', 'error']:
            with self.subTest(status=status):
                gates = self.book(status)
                state = {'claude': dict(self.record)}
                with patch('monitor.generation', return_value='same'), \
                     patch('monitor.collect_claude', side_effect=MonitorError(status, 'fixture')) as fetch:
                    value, state['claude'] = collect_one('claude', 'cn', None, state, gates=gates)
                    deadline = value['nextQueryAt']
                    # A restart, lost UI snapshot and repeated refreshes must keep
                    # the same reading without contacting Claude or extending time.
                    gates = self.book(status)
                    for _ in range(5):
                        value, state['claude'] = collect_one('claude', 'cn', None, state, True, gates=gates)
                        self.assertEqual(value['windows'], self.good['windows'])
                        self.assertEqual(value['fetchedAt'], 1000)
                        self.assertEqual(value['status'], 'stale')
                        self.assertEqual(value['liveStatus'], status)
                        self.assertEqual(value['queryStatus'], 'cooldown')
                        self.assertEqual(value['nextQueryAt'], deadline)
                        self.assertTrue(value['historical'])
                    fetch.assert_called_once()
                self.assertTrue(state['claude']['authBlocked'])
                self.assertEqual(state['claude']['lastGood'], self.good)
                self.assertEqual(gates.get('claude')['requestCount'], 1)

    def test_existing_cooldown_recovers_zero_without_a_local_credential_file(self):
        self.good['windows'][0]['remainingPercent'] = 0
        gates = self.book()
        gates.reserve('claude'); gates.failure('claude', MonitorError('rate_limited', 'fixture'))
        with patch('monitor.generation', return_value=None), patch('monitor.collect_claude') as fetch:
            value, _ = collect_one('claude', 'cn', None, {'claude': self.record}, gates=gates)
        fetch.assert_not_called()
        self.assertEqual(value['windows'][0]['remainingPercent'], 0)
        self.assertEqual(value['fetchedAt'], 1000)
        self.assertEqual(value['status'], 'stale')
        self.assertTrue(value['historical'])

    def test_cooldown_without_any_success_does_not_invent_quota(self):
        gates = self.book()
        gates.reserve('claude'); gates.failure('claude', MonitorError('rate_limited', 'fixture'))
        with patch('monitor.generation', return_value=None), patch('monitor.collect_claude') as fetch:
            value, _ = collect_one('claude', 'cn', None, {}, gates=gates)
        fetch.assert_not_called()
        self.assertEqual(value['windows'], [])
        self.assertIsNone(value['fetchedAt'])

    def test_current_login_rejection_does_not_claim_a_usable_account(self):
        gates = self.book()
        with patch('monitor.generation', return_value='same'), \
             patch('monitor.collect_claude', side_effect=MonitorError('auth_required', 'fixture')):
            value, record = collect_one('claude', 'cn', None, {'claude': self.record}, gates=gates)
            cached, _ = collect_one('claude', 'cn', value, {'claude': record}, gates=gates)
        self.assertEqual(value['windows'], [])
        self.assertEqual(cached['windows'], [])
        self.assertEqual(record['lastGood'], self.good)

    def test_next_success_replaces_history_and_clears_login_block(self):
        latest = {**self.good, 'fetchedAt': self.now, 'windows': [window('short', 'Session', remaining_percent=31, minutes=300)]}
        with patch('monitor.generation', return_value='same'), patch('monitor.collect_claude', return_value=latest):
            value, record = collect_one('claude', 'cn', None, {'claude': self.record}, gates=self.book())
        self.assertEqual(value['windows'][0]['remainingPercent'], 31)
        self.assertEqual(record['lastGood']['fetchedAt'], self.now)
        self.assertFalse(record['authBlocked'])

class AuthorizationStatusTests(unittest.TestCase):
    def test_timeout_is_not_permission_required(self):
        with patch.dict('os.environ',{'MONITOR_KEYCHAIN_HELPER':'/synthetic/helper'}),patch('credentials.run',side_effect=MonitorError('network_error','timeout')):
            with self.assertRaises(MonitorError) as error:keychain('Claude Code-credentials')
        self.assertEqual(error.exception.status,'unavailable')
    def test_explicit_denial_is_permission_required(self):
        with patch.dict('os.environ',{'MONITOR_KEYCHAIN_HELPER':'/synthetic/helper'}),patch('credentials.run',return_value=(3,b'')):
            with self.assertRaises(MonitorError) as error:keychain('Claude Code-credentials')
        self.assertEqual(error.exception.status,'permission_required')
    def test_missing_key_is_not_a_permission_error(self):
        with patch.dict('os.environ',{'MONITOR_KEYCHAIN_HELPER':'/synthetic/helper'}),patch('credentials.run',return_value=(2,b'')):
            self.assertIsNone(keychain('Claude Code-credentials'))
    def test_locked_keychain_is_unavailable_not_denied(self):
        with patch.dict('os.environ',{'MONITOR_KEYCHAIN_HELPER':'/synthetic/helper'}),patch('credentials.run',return_value=(5,b'')):
            with self.assertRaises(MonitorError) as error:keychain('Claude Code-credentials')
        self.assertEqual(error.exception.status,'unavailable')
        self.assertIn('锁定',error.exception.message)
    def test_component_failure_is_not_denied(self):
        with patch.dict('os.environ',{'MONITOR_KEYCHAIN_HELPER':'/synthetic/helper'}),patch('credentials.run',return_value=(4,b'')):
            with self.assertRaises(MonitorError) as error:keychain('Claude Code-credentials')
        self.assertEqual(error.exception.status,'unavailable')

if __name__=='__main__':unittest.main()
