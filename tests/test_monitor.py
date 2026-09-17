"""Offline regression tests. All credentials below are explicitly synthetic fixtures."""
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'collector'))
from core import MonitorError, number, timestamp, window, atomic_json, read_json, duration_label
from network import validate_url, NoRedirect
from kimi_provider import parse_kimi, renew, validate_official_origin
from kimi_lock import KimiRefreshLock
from codex_provider import parse_codex
from other_providers import parse_claude, parse_glm, parse_copilot
from antigravity_provider import parse_antigravity
from monitor import error_result, public_result

class NumericTests(unittest.TestCase):
    def test_remaining_ratio(self): self.assertEqual(window('a','a',limit=200,remaining=50)['remainingPercent'],25)
    def test_used_ratio(self): self.assertEqual(window('a','a',limit=200,used=150)['remainingPercent'],25)
    def test_used_percent(self): self.assertEqual(window('a','a',used_percent=26)['remainingPercent'],74)
    def test_zero_is_real(self): self.assertEqual(window('a','a',remaining_percent=0)['remainingPercent'],0)
    def test_full_is_real(self): self.assertEqual(window('a','a',remaining_percent=100)['remainingPercent'],100)
    def test_missing_is_not_full(self): self.assertIsNone(window('a','a',limit=100)['remainingPercent'])
    def test_zero_denominator(self): self.assertIsNone(window('a','a',limit=0,used=0)['remainingPercent'])
    def test_negative_denominator(self): self.assertIsNone(window('a','a',limit=-1,remaining=-1)['remainingPercent'])
    def test_nan_infinity_rejected(self):
        for value in ('NaN',float('inf'),True,None): self.assertIsNone(number(value))
    def test_unlimited_is_not_full(self): self.assertIsNone(window('a','a',remaining_percent=100,unlimited=True)['remainingPercent'])
    def test_exhaustion_clamped(self): self.assertEqual(window('a','a',used_percent=120)['remainingPercent'],0)
    def test_timestamp_millis(self): self.assertEqual(timestamp(1700000000000),1700000000)
    def test_iso_timestamp(self): self.assertEqual(timestamp('2026-01-01T00:00:00Z'),1767225600)
    def test_real_period_label(self): self.assertEqual(duration_label(43200),'30 天窗口')

class ProviderTests(unittest.TestCase):
    def test_kimi_windows(self):
        result = parse_kimi({'usage':{'limit':'100','remaining':'74'},'limits':[{'window':{'duration':300,'timeUnit':'TIME_UNIT_MINUTE'},'detail':{'limit':'100','used':'20'}}]})
        self.assertEqual([x['remainingPercent'] for x in result],[80,74])
        self.assertEqual([x['durationMinutes'] for x in result],[300,10080])
    def test_kimi_non_5h_window(self):
        result=parse_kimi({'limits':[{'window':{'duration':2,'timeUnit':'TIME_UNIT_HOUR'},'detail':{'limit':20,'remaining':10}}]})
        self.assertEqual(result[0]['durationMinutes'],120)
    def test_kimi_missing_summary(self):
        result=parse_kimi({'limits':[{'window':{},'detail':{}}]})
        self.assertEqual(len(result),1); self.assertIsNone(result[0]['remainingPercent'])
    def test_kimi_no_payload(self):
        with self.assertRaises(MonitorError): parse_kimi({})
    def test_codex_free_30_day(self):
        result=parse_codex({'rateLimits':{'primary':{'usedPercent':100,'windowDurationMins':43200},'secondary':None}})
        self.assertEqual(len(result),1); self.assertEqual(result[0]['label'],'30 天窗口'); self.assertEqual(result[0]['remainingPercent'],0)
    def test_codex_weekly_primary_not_session(self):
        result=parse_codex({'rateLimits':{'primary':{'usedPercent':40,'windowDurationMins':10080}}})
        self.assertEqual(result[0]['label'],'每周')
    def test_codex_missing_not_full(self): self.assertEqual(parse_codex({}),[])
    def test_codex_mapped_limits(self):
        result=parse_codex({'rateLimitsByLimitId':{'codex':{'primary':{'usedPercent':5,'windowDurationMins':300}}}})
        self.assertEqual(result[0]['remainingPercent'],95)
    def test_claude_null_window(self): self.assertEqual(parse_claude({'five_hour':None,'seven_day':{'utilization':None}}),[])
    def test_claude_scoped(self):
        result=parse_claude({'five_hour':{'utilization':0},'seven_day_opus':{'utilization':100}})
        self.assertEqual([x['remainingPercent'] for x in result],[100,0])
    def test_glm_five_hour_week(self):
        result=parse_glm({'data':{'limits':[{'type':'TOKENS_LIMIT','unit':3,'number':5,'percentage':20},{'type':'CREDIT_LIMIT','unit':6,'number':1,'usage':400,'remaining':300}]}})
        self.assertEqual([x['durationMinutes'] for x in result],[300,10080]); self.assertEqual([x['remainingPercent'] for x in result],[80,75])
    def test_glm_mcp_month_not_minute(self):
        result=parse_glm({'data':{'limits':[{'type':'TIME_LIMIT','unit':5,'number':1,'percentage':5}]}})
        self.assertEqual(result[0]['label'],'MCP · 本月'); self.assertIsNone(result[0]['durationMinutes'])
    def test_glm_missing_not_full(self): self.assertEqual(parse_glm({}),[])
    def test_copilot_placeholder(self):
        self.assertEqual(parse_copilot({'quota_snapshots':{'premium_interactions':{'entitlement':-1,'percent_remaining':100}}}),[])
    def test_copilot_unlimited(self):
        result=parse_copilot({'quota_snapshots':{'chat':{'unlimited':True,'percent_remaining':0}}})
        self.assertIsNone(result[0]['remainingPercent']); self.assertTrue(result[0]['isUnlimited'])
    def test_copilot_real_percent(self):
        result=parse_copilot({'quota_snapshots':{'premium_interactions':{'entitlement':200,'percent_remaining':99.3}}})
        self.assertEqual(result[0]['remainingPercent'],99.3); self.assertIsNone(result[0]['durationMinutes'])
    def test_antigravity_missing_not_full(self): self.assertEqual(parse_antigravity({'groups':[{'buckets':[{'remainingFraction':None}]}]}),[])
    def test_antigravity_model_not_week(self):
        result=parse_antigravity({'userStatus':{'cascadeModelConfigData':{'clientModelConfigs':[{'label':'Gemini','quotaInfo':{'remainingFraction':0.5}}]}}})
        self.assertEqual(result[0]['remainingPercent'],50); self.assertIsNone(result[0]['durationMinutes'])
    def test_antigravity_nested_summary(self):
        result=parse_antigravity({'summary':{'groups':[{'displayName':'Gemini','buckets':[{'bucketId':'weekly','remaining':{'case':'remainingFraction','value':0.25}},{'bucketId':'disabled','remainingFraction':1,'disabled':True}]}]}})
        self.assertEqual(len(result),1); self.assertEqual(result[0]['durationMinutes'],10080)

class SafetyTests(unittest.TestCase):
    def test_allowed_provider_endpoint(self): validate_url('https://api.kimi.com/coding/v1/usages')
    def test_other_targets_blocked(self):
        for url in ['http://api.kimi.com/coding/v1/usages','https://attacker.invalid/coding/v1/usages','https://api.kimi.com/coding/v1/chat/completions','https://user:pass@api.kimi.com/coding/v1/usages','https://api.kimi.com/coding/v1/usages?token=abc']:
            with self.assertRaises(MonitorError): validate_url(url)
    def test_loopback_only(self):
        with self.assertRaises(MonitorError): validate_url('https://10.0.0.1:999/exa.language_server_pb.LanguageServerService/GetUserStatus',local=True)
    def test_redirect_blocked(self):
        with self.assertRaises(MonitorError): NoRedirect().redirect_request(None,None,302,'',{},'https://other.invalid')
    def test_private_atomic_file(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'state.json'; atomic_json(path,{'x':3})
            self.assertEqual(stat.S_IMODE(path.stat().st_mode),0o600); self.assertEqual(read_json(path),{'x':3})
    def test_stale_only_network_same_identity(self):
        old={'status':'ok','windows':[window('a','a',remaining_percent=30)],'fetchedAt':1,'source':'fixture'}
        self.assertEqual(error_result('kimi',MonitorError('network_error','offline'),old,True)['status'],'stale')
        self.assertEqual(error_result('kimi',MonitorError('auth_required','login'),old,True)['windows'],[])
        self.assertTrue(error_result('kimi',MonitorError('network_error','offline'),old,False)['historical'])
    def test_no_private_fields(self):
        self.assertEqual(public_result({'id':'kimi','_identity':'private-hash','access_token':'synthetic-test'}),{'id':'kimi'})
    def test_live_kimi_lock_not_stolen(self):
        with tempfile.TemporaryDirectory() as home:
            path=Path(home)/'oauth/kimi-code.lock'
            with KimiRefreshLock(home):
                with self.assertRaises(MonitorError):
                    with KimiRefreshLock(home,wait_seconds=0.02): pass
                self.assertTrue(path.is_dir())
            self.assertFalse(path.exists())
    def test_stale_lock_recovered(self):
        with tempfile.TemporaryDirectory() as home:
            path=Path(home)/'oauth/kimi-code.lock'; path.mkdir(parents=True)
            os.utime(path,(time.time()-60,time.time()-60))
            with KimiRefreshLock(home): self.assertTrue(path.is_dir())
            self.assertFalse(path.exists())
    def test_kimi_endpoint_override_rejected(self):
        with tempfile.TemporaryDirectory() as home, patch.dict(os.environ,{'KIMI_CODE_BASE_URL':'https://other.invalid'}):
            with self.assertRaises(MonitorError): validate_official_origin(Path(home))

class RenewalTests(unittest.TestCase):
    def test_coordinated_renewal(self):
        with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as support:
            root=Path(home); path=root/'credentials/kimi-code.json'
            old={'access_token':'synthetic-access','refresh_token':'synthetic-refresh','expires_at':1,'preserve':'yes'}
            atomic_json(path,old)
            with patch('kimi_provider.SUPPORT',Path(support)), patch('kimi_provider.request_json',return_value={'access_token':'synthetic-new-access','refresh_token':'synthetic-new-refresh','expires_in':3600}) as request:
                new=renew(root,old)
                self.assertEqual(new['access_token'],'synthetic-new-access'); self.assertEqual(new['preserve'],'yes')
                self.assertEqual(read_json(path),new); self.assertEqual(request.call_count,1)
                self.assertFalse((root/'oauth/kimi-code.lock').exists())
    def test_peer_winner_not_overwritten(self):
        with tempfile.TemporaryDirectory() as home:
            root=Path(home); old={'access_token':'synthetic-old'}
            winner={'access_token':'synthetic-winner','expires_at':time.time()+3600}
            atomic_json(root/'credentials/kimi-code.json',winner)
            with patch('kimi_provider.request_json') as request:
                self.assertEqual(renew(root,old),winner); request.assert_not_called()
    def test_invalid_grant_not_retried(self):
        with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as support:
            root=Path(home); old={'access_token':'synthetic-expired','refresh_token':'synthetic-rejected','expires_at':1}
            atomic_json(root/'credentials/kimi-code.json',old)
            with patch('kimi_provider.SUPPORT',Path(support)), patch('kimi_provider.request_json',side_effect=MonitorError('error','fixture',http_status=400,oauth_code='invalid_grant')) as request:
                for _ in range(2):
                    with self.assertRaises(MonitorError): renew(root,old)
                self.assertEqual(request.call_count,1)
                self.assertEqual(read_json(root/'credentials/kimi-code.json'),old)
    def test_network_failure_preserves_login(self):
        with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as support:
            root=Path(home); old={'access_token':'synthetic-expired','refresh_token':'synthetic-refresh','expires_at':1}
            atomic_json(root/'credentials/kimi-code.json',old)
            with patch('kimi_provider.SUPPORT',Path(support)), patch('kimi_provider.request_json',side_effect=MonitorError('network_error','fixture')):
                with self.assertRaises(MonitorError): renew(root,old)
                self.assertEqual(read_json(root/'credentials/kimi-code.json'),old)
                self.assertFalse((Path(support)/'kimi-refresh-state.json').exists())


class FinalRegressionTests(unittest.TestCase):
    def test_claude_requires_explicit_keychain_grant(self):
        from other_providers import claude_credentials
        with patch('other_providers.read_json',return_value={}), patch.dict(os.environ,{'MONITOR_CLAUDE_KEYCHAIN_ALLOWED':'0'}), patch('other_providers.keychain') as helper:
            with self.assertRaises(MonitorError) as caught: claude_credentials()
            self.assertEqual(caught.exception.status,'permission_required')
            helper.assert_not_called()
    def test_kimi_never_renews_twice_in_one_round(self):
        from kimi_provider import collect_kimi
        old={'access_token':'synthetic-old','expires_at':1}
        fresh={'access_token':'synthetic-fresh','expires_at':time.time()+3000}
        with patch('kimi_provider.own_key',return_value=None), patch.dict(os.environ,{'KIMI_CODE_API_KEY':''}), patch('kimi_provider.validate_official_origin'), patch('kimi_provider.device_headers',return_value={}), patch('kimi_provider.load_cli',side_effect=[old,fresh]), patch('kimi_provider.renew',return_value=fresh) as grant, patch('kimi_provider.request_json',side_effect=MonitorError('auth_required','fixture',http_status=401)):
            with self.assertRaises(MonitorError): collect_kimi()
            self.assertEqual(grant.call_count,1)

if __name__=='__main__': unittest.main(verbosity=2)
