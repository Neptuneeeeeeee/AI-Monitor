"""Offline only: HTTP responses, clocks, credentials and provider calls are mocked."""
import contextlib
import email.utils
import io
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'collector'))
from core import MonitorError, atomic_json, read_json, window
from rate_limits import retry_delay, http_error, rpc_error, parse_cli_http, has_rate_signal
from scheduling import GateBook, MIN_INTERVAL, interval_for, backoff_seconds
import monitor
import antigravity_provider
import other_providers


class RateHeaderTests(unittest.TestCase):
    def test_delay_seconds(self): self.assertEqual(retry_delay({'Retry-After': '120'}, now=1000), 120)
    def test_long_delay_is_not_capped(self): self.assertEqual(retry_delay({'Retry-After':'86400'}, now=1000),86400)
    def test_http_date(self):
        self.assertEqual(retry_delay({'retry-after':email.utils.formatdate(4600,usegmt=True)},now=1000),3600)
    def test_server_clock_does_not_shorten_wait(self):
        h={'Retry-After':email.utils.formatdate(4600,usegmt=True),'Date':email.utils.formatdate(1000,usegmt=True)}
        self.assertEqual(retry_delay(h,now=3000),3600)
    def test_invalid_delay(self):
        for value in ('nonsense','-10','NaN','1.5'):
            self.assertEqual(retry_delay({'Retry-After':value},now=1000),0)
    def test_past_date(self): self.assertEqual(retry_delay({'Retry-After':email.utils.formatdate(900,usegmt=True)},now=1000),0)
    def test_github_reset(self):
        self.assertEqual(retry_delay({'X-RateLimit-Remaining':'0','X-RateLimit-Reset':'4600'},now=1000),3600)
    def test_github_unused_reset_ignored(self):
        self.assertEqual(retry_delay({'X-RateLimit-Remaining':'2','X-RateLimit-Reset':'4600'},now=1000),0)
    def test_larger_header_wins(self):
        self.assertEqual(retry_delay({'Retry-After':'100','X-RateLimit-Remaining':'0','X-RateLimit-Reset':'4600'},now=1000),3600)
    def test_429_not_auth_failure(self): self.assertEqual(http_error(429).status,'rate_limited')
    def test_github_403_quota_headers(self): self.assertEqual(http_error(403,{'x-ratelimit-remaining':'0'}).status,'rate_limited')
    def test_github_secondary_403(self): self.assertEqual(http_error(403,payload={'message':'You exceeded a secondary rate limit.'}).status,'rate_limited')
    def test_plain_403_not_misclassified(self): self.assertEqual(http_error(403).status,'permission_required')
    def test_503_honors_retry_after(self): self.assertEqual(http_error(503,{'Retry-After':'7200'}).retry_after,7200)
    def test_oauth_invalid_grant_preserved(self): self.assertEqual(http_error(400,payload={'error':'invalid_grant'}).oauth_code,'invalid_grant')
    def test_rpc_429(self): self.assertEqual(rpc_error({'code':-32000,'message':'HTTP 429 Too Many Requests'}).status,'rate_limited')
    def test_nested_rpc_429(self): self.assertEqual(rpc_error({'data':{'httpStatus':429,'retryAfterSeconds':3600}}).retry_after,3600)
    def test_unknown_rpc_not_login(self): self.assertEqual(rpc_error({'message':'temporarily unavailable'}).status,'network_error')
    def test_model_quota_is_not_query_failure(self): self.assertFalse(has_rate_signal({'rateLimits':{'primary':{'usedPercent':100}}}))
    def test_cli_http_success(self):
        status,h,p=parse_cli_http(b'HTTP/2.0 200 OK\r\nContent-Type: application/json\r\n\r\n{"quota_snapshots":{}}')
        self.assertEqual(status,200);self.assertIn('quota_snapshots',p)
    def test_cli_http_429(self):
        status,h,p=parse_cli_http('HTTP/2.0 429 Too Many Requests\nRetry-After: 4000\nSet-Cookie: not-retained\n\n{"message":"fixture"}')
        self.assertEqual(http_error(status,h,p).retry_after,4000);self.assertNotIn('set-cookie',h)
    def test_cli_bare_error(self):
        status,h,p=parse_cli_http('{"status":"429"}')
        self.assertEqual(status,0);self.assertTrue(has_rate_signal(p))


class GateTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'request-gates.json';self.now=1800000000.0
        self.book=GateBook(self.path,clock=lambda:self.now,jitter=lambda delay:0)
    def tearDown(self):self.tmp.cleanup()
    def test_all_provider_floors(self):
        self.assertEqual(MIN_INTERVAL,{'claude':600,'kimi':300,'codex':300,'glm':300,'copilot':600,'antigravity':300,'cursor':600,'minimax':600,'windsurf':300,'kiro':900})
    def test_slow_preference_respected(self):self.assertEqual(interval_for('kimi',1800),1800)
    def test_fast_preference_cannot_lower_floor(self):self.assertEqual(interval_for('claude',1),600)
    def test_recovery_ramp_converges_to_provider_interval(self):
        # After real rate limits the ramp is a multiple of this provider's own floor,
        # halving on each success until it reaches that floor again.
        self.book.reserve('claude');self.book.failure('claude',MonitorError('rate_limited','fixture'))
        self.book.providers['claude']['rateFailures']=2
        self.now=self.book.get('claude')['nextAttempt']+1
        self.assertTrue(self.book.reserve('claude')[0])
        self.assertEqual(self.book.success('claude')['intervalSeconds'],1200)
        self.now=self.book.get('claude')['nextAttempt']+1
        self.assertTrue(self.book.reserve('claude')[0])
        self.assertEqual(self.book.success('claude')['intervalSeconds'],600)
    def test_rate_limit_cooldown_is_unchanged_by_the_lower_floor(self):
        self.book.reserve('claude');gate=self.book.failure('claude',MonitorError('rate_limited','fixture'))
        self.assertEqual(gate['nextAttempt']-self.now,900)
    def test_increasing_selected_interval_extends_existing_gate(self):
        self.book.reserve('kimi');self.book.success('kimi');self.now+=400
        allowed,gate=self.book.reserve('kimi',requested=1800)
        self.assertFalse(allowed);self.assertEqual(gate['nextAttempt'],1800001800.0)
    def test_success_blocks_burst_for_every_provider(self):
        for pid in MIN_INTERVAL:
            with self.subTest(pid=pid):
                self.assertTrue(self.book.reserve(pid)[0]);self.book.success(pid)
                for _ in range(300):self.assertFalse(self.book.reserve(pid)[0])
                self.assertEqual(self.book.get(pid)['requestCount'],1)
    def test_failure_blocks_burst_for_every_provider(self):
        for pid in MIN_INTERVAL:
            self.book.reserve(pid);self.book.failure(pid,MonitorError('rate_limited','fixture'))
            for _ in range(100):self.assertFalse(self.book.reserve(pid)[0])
            self.assertGreaterEqual(self.book.get(pid)['nextAttempt'],self.now+900)
    def test_provider_independence(self):
        self.book.reserve('claude');self.book.failure('claude',MonitorError('rate_limited','fixture'))
        self.assertTrue(self.book.reserve('kimi')[0])
    def test_restart_preserves_gate(self):
        self.book.reserve('kimi');self.book.failure('kimi',MonitorError('rate_limited','fixture'))
        restarted=GateBook(self.path,clock=lambda:self.now,jitter=lambda _:0)
        self.assertFalse(restarted.reserve('kimi')[0])
    def test_cache_removal_does_not_remove_gate(self):
        self.book.reserve('claude');self.book.failure('claude',MonitorError('rate_limited','fixture'))
        restarted=GateBook(self.path,legacy={},previous={},clock=lambda:self.now)
        self.assertFalse(restarted.reserve('claude')[0])
    def test_crash_lease_survives_without_result(self):
        self.book.reserve('codex')
        restarted=GateBook(self.path,clock=lambda:self.now)
        self.assertFalse(restarted.reserve('codex')[0])
    def test_exponential_limits(self):
        delays=[]
        for _ in range(5):
            self.assertTrue(self.book.reserve('kimi')[0])
            gate=self.book.failure('kimi',MonitorError('rate_limited','fixture'))
            delays.append(gate['nextAttempt']-self.now);self.now=gate['nextAttempt']+1
        self.assertEqual(delays,[900,1800,3600,7200,7200])
    def test_server_wait_longer_than_backoff(self):
        self.book.reserve('kimi');gate=self.book.failure('kimi',MonitorError('rate_limited','fixture',retry_after=86400))
        self.assertEqual(gate['nextAttempt']-self.now,86400)
    def test_jitter_only_delays(self):
        b=GateBook(self.path,clock=lambda:self.now,jitter=lambda _:29)
        b.reserve('kimi');self.assertEqual(b.success('kimi')['nextAttempt']-self.now,329)
    def test_expired_gate_allows_one_query(self):
        self.book.reserve('kimi');self.book.success('kimi');self.now+=301
        self.assertTrue(self.book.reserve('kimi')[0]);self.assertFalse(self.book.reserve('kimi')[0])
    def test_legacy_limit_gets_quiet_period_once(self):
        b=GateBook(self.path,legacy={'claude':{'status':'rate_limited','failures':3,'nextAttempt':self.now-1}},clock=lambda:self.now,jitter=lambda _:0)
        first=b.get('claude')['nextAttempt'];self.assertGreaterEqual(first,self.now+900)
        self.now+=60
        self.assertEqual(GateBook(self.path,clock=lambda:self.now).get('claude')['nextAttempt'],first)
    def test_simultaneous_reservation_single_winner(self):
        results=[]
        threads=[threading.Thread(target=lambda:results.append(self.book.reserve('kimi')[0])) for _ in range(20)]
        for t in threads:t.start()
        for t in threads:t.join()
        self.assertEqual(sum(results),1)
    def test_file_private(self):
        self.book.reserve('kimi');self.assertEqual(self.path.stat().st_mode & 0o777,0o600)


class CoordinatorTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name);self.now=1800000000.0
        self.book=GateBook(self.path/'request-gates.json',clock=lambda:self.now,jitter=lambda _:0)
        self.good={'id':'kimi','name':'Kimi','status':'ok','source':'fixture','message':'','fetchedAt':self.now,'attemptedAt':self.now,'windows':[window('session','Session',remaining_percent=40,minutes=300)]}
    def tearDown(self):self.tmp.cleanup()
    def test_force_100_times_makes_one_adapter_call(self):
        state={};previous=None
        with patch('monitor.generation',return_value='same'),patch('monitor.collect_kimi',return_value=self.good) as fetch:
            for _ in range(100):
                previous,record=monitor.collect_one('kimi','cn',previous,state,True,gates=self.book)
                state['kimi']=record
            self.assertEqual(fetch.call_count,1);self.assertEqual(previous['fetchedAt'],self.now);self.assertEqual(previous['attemptedAt'],self.now)
    def test_credential_changes_cannot_bypass_429(self):
        state={};previous=None
        with patch('monitor.generation') as gen,patch('monitor.collect_kimi',side_effect=MonitorError('rate_limited','fixture')) as fetch:
            for i in range(100):
                gen.return_value=str(i)
                previous,record=monitor.collect_one('kimi','cn',previous,state,True,gates=self.book)
                state['kimi']=record
            self.assertEqual(fetch.call_count,1);self.assertEqual(previous['windows'],[])
    def test_unknown_generation_still_blocks(self):
        with patch('monitor.generation',return_value=None),patch('monitor.collect_antigravity',side_effect=MonitorError('rate_limited','fixture')) as fetch:
            for _ in range(50):monitor.collect_one('antigravity','cn',None,{},True,gates=self.book)
            self.assertEqual(fetch.call_count,1)
    def test_limit_preserves_known_last_good_as_stale(self):
        record={'generation':'same','region':'cn','result':self.good}
        with patch('monitor.generation',return_value='same'),patch('monitor.collect_kimi',side_effect=MonitorError('rate_limited','fixture')):
            value,_=monitor.collect_one('kimi','cn',self.good,{'kimi':record},True,gates=self.book)
        self.assertEqual(value['status'],'stale');self.assertEqual(value['fetchedAt'],self.now);self.assertEqual(value['windows'][0]['remainingPercent'],40)
    def test_auth_failure_never_preserves_quota(self):
        with patch('monitor.generation',return_value='same'),patch('monitor.collect_kimi',side_effect=MonitorError('auth_required','fixture')):
            value,_=monitor.collect_one('kimi','cn',self.good,{'kimi':{'generation':'same','result':self.good}},True,gates=self.book)
        self.assertEqual(value['windows'],[])
    def test_disabled_provider_and_no_cache_do_not_erase_cooldown(self):
        def invoke(arguments):
            with patch.object(sys,'argv',['monitor.py']+arguments),contextlib.redirect_stdout(io.StringIO()):self.assertEqual(monitor.main(),0)
        with patch('monitor.SUPPORT',self.path),patch('monitor.generation',return_value='same'),patch('monitor.collect_kimi',side_effect=MonitorError('rate_limited','fixture')) as limited,patch('monitor.collect_claude',return_value={**self.good,'id':'claude','name':'Claude'}):
            invoke(['--providers','kimi','--force'])
            invoke(['--providers','claude','--force'])
            self.assertIn('kimi',read_json(self.path/'provider-state.json'))
            invoke(['--providers','kimi','--no-cache','--force'])
            self.assertEqual(limited.call_count,1)
    def test_antigravity_429_stops_fallback_immediately(self):
        with patch('antigravity_provider.SUPPORT',self.path),patch('antigravity_provider.local_servers',return_value=[(1234,'synthetic-csrf'),(5678,'synthetic-csrf')]),patch('antigravity_provider.request_json',side_effect=MonitorError('rate_limited','fixture',http_status=429,retry_after=3600)) as fetch:
            with self.assertRaises(MonitorError) as caught:antigravity_provider.collect_antigravity()
            self.assertEqual(fetch.call_count,1);self.assertEqual(caught.exception.retry_after,3600)
    def test_claude_429_does_not_reread_login_or_refresh(self):
        with patch('other_providers.claude_credentials',return_value={'accessToken':'synthetic-only'}) as creds,patch('other_providers.request_json',side_effect=MonitorError('rate_limited','fixture',http_status=429)) as fetch:
            with self.assertRaises(MonitorError):other_providers.collect_claude()
            self.assertEqual(fetch.call_count,1);self.assertEqual(creds.call_count,1)
    def test_copilot_cli_429_preserves_delay(self):
        raw=b'HTTP/2.0 429 Too Many Requests\r\nRetry-After: 7200\r\n\r\n{"message":"fixture"}'
        with patch('other_providers.own_key',return_value=None),patch('other_providers.executable',return_value='synthetic-gh'),patch('other_providers.run',return_value=(1,raw)):
            with self.assertRaises(MonitorError) as caught:other_providers.collect_copilot()
            self.assertEqual(caught.exception.status,'rate_limited');self.assertEqual(caught.exception.retry_after,7200)


if __name__=='__main__':unittest.main(verbosity=2)
