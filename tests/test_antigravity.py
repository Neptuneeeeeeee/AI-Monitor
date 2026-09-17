"""Local-discovery regression tests. Authentication values are synthetic fixtures."""
import sys
from pathlib import Path
from unittest import TestCase, main
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'collector'))
from antigravity_provider import parse_listeners, official_processes, csrf_for, local_servers, bucket_minutes, parse_antigravity
from core import MonitorError

APP = '/Applications/Antigravity.app/Contents/Resources/bin/language_server'
IDE = '/Applications/Antigravity IDE.app/Contents/Resources/bin/language_server_macos_arm'

class DiscoveryTests(TestCase):
    def test_numeric_ipv4(self):
        self.assertEqual(parse_listeners('p99\nn127.0.0.1:56729\nn127.0.0.1:56730\n'), [56729,56730])
    def test_no_remote_interface_probes(self):
        self.assertEqual(parse_listeners('n192.168.1.4:9000\nnexample.com:9000'), [])
    def test_wildcard_and_duplicates(self):
        self.assertEqual(parse_listeners('n*:9000\nn0.0.0.0:9000\nn127.0.0.1:0\nn127.0.0.1:65536'), [9000])
    def test_exact_official_binary(self):
        self.assertEqual(official_processes('99 '+APP+'\n100 /tmp/Antigravity.app/language_server\n101 /Applications/Antigravity.app/fake'), [(99,APP)])
    def test_spaces_in_ide_path(self):
        self.assertEqual(official_processes('100 '+IDE), [(100,IDE)])
        self.assertEqual(csrf_for(IDE+' --csrf_token synthetic-fixture --other 3',IDE),'synthetic-fixture')
    def test_flag_equal_syntax(self):
        self.assertEqual(csrf_for(APP+' --csrf_token=synthetic-fixture',APP),'synthetic-fixture')
    def test_missing_auth_not_sent(self):
        self.assertIsNone(csrf_for(APP+' --other 3',APP))
    def test_requires_numeric_lsof_regression(self):
        def fake_run(args, **kw):
            if 'pid=,comm=' in args:return 0,('99 '+APP).encode()
            if 'command=' in args:return 0,(APP+' --csrf_token synthetic-fixture').encode()
            self.assertIn('-nP',args)  # Without this macOS returns localhost:port.
            return 0,b'p99\nn127.0.0.1:56729\n'
        with patch('antigravity_provider.run',side_effect=fake_run):
            self.assertEqual(local_servers(),[(56729,'synthetic-fixture')])
    def test_running_but_no_ports_is_specific(self):
        with patch('antigravity_provider.run',side_effect=[(0,('99 '+APP).encode()),(0,(APP+' --csrf_token fixture').encode()),(1,b'')]):
            with self.assertRaises(MonitorError) as error:local_servers()
            self.assertIn('监听端口',error.exception.message)
    def test_closed_app(self):
        with patch('antigravity_provider.run',return_value=(0,b'99 /usr/bin/python3')):
            self.assertEqual(local_servers(),[])

class PayloadTests(TestCase):
    def test_five_hour_spellings(self):
        for label in ['Five Hour Limit Remaining','5-hour','five_hour','5h','5 hours']:
            self.assertEqual(bucket_minutes({'displayName':label}),300)
    def test_weekly_is_not_5h(self):
        self.assertEqual(bucket_minutes({'displayName':'Weekly Limit Remaining'}),10080)
    def test_unknown_period_not_invented(self):
        self.assertIsNone(bucket_minutes({'displayName':'Model pool'}))
    def test_compact_names_and_real_zero(self):
        p={'groups':[{'displayName':'Gemini Models','buckets':[{'bucketId':'five_hour','remainingFraction':0}]},{'displayName':'Claude and GPT models','buckets':[{'bucketId':'weekly','remainingFraction':1}]}]}
        w=parse_antigravity(p)
        self.assertEqual([v['label'] for v in w],['Gemini · Session','Claude · Weekly'])
        self.assertEqual([v['remainingPercent'] for v in w],[0,100])
    def test_disabled_unknown_not_full(self):
        self.assertEqual(parse_antigravity({'groups':[{'buckets':[{'bucketId':'weekly'},{'bucketId':'5h','disabled':True,'remainingFraction':1}]}]}),[])
    def test_fraction_outside_range_ignored(self):
        self.assertEqual(parse_antigravity({'groups':[{'buckets':[{'remainingFraction':-1},{'remainingFraction':1.2}]}]}),[])

if __name__=='__main__':main(verbosity=2)
