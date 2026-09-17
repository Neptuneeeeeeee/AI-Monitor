"""Regression for a live-observed zero-capacity Cursor plan (no real credentials)."""
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'collector'))
import extended_plans as E
import monitor
from scheduling import GateBook
from core import window

class CursorZeroAllowanceTests(unittest.TestCase):
    def payload(self, **overrides):
        return {'membershipType':'free','individualUsage':{'plan':{
            'enabled':True,'limit':0,'used':0,'remaining':0,
            'totalPercentUsed':0,'autoPercentUsed':0,'apiPercentUsed':0,**overrides}}}
    def test_zero_capacity_never_becomes_three_full_pools(self):
        self.assertEqual(E.parse_cursor(self.payload()),[])
    def test_invalid_explicit_capacity_rejects_percentage_placeholders(self):
        for bad in [None,True,False,-1,'bad',float('nan'),float('inf')]:
            with self.subTest(limit=bad):self.assertEqual(E.parse_cursor(self.payload(limit=bad)),[])
    def test_string_zero_capacity_is_not_a_full_plan(self):
        self.assertEqual(E.parse_cursor(self.payload(limit='0')),[])
    def test_positive_capacity_zero_usage_can_be_full(self):
        windows=E.parse_cursor(self.payload(limit=100,remaining=100))
        self.assertEqual(windows[0]['remainingPercent'],100)
    def test_positive_capacity_exhausted_is_real_zero(self):
        windows=E.parse_cursor(self.payload(limit=100,used=100,totalPercentUsed=100,autoPercentUsed=100,apiPercentUsed=100))
        self.assertTrue(windows)
        self.assertTrue(all(w['remainingPercent']==0 for w in windows))
    def test_percentage_only_contract_remains_supported(self):
        payload=self.payload()
        del payload['individualUsage']['plan']['limit']
        self.assertEqual(E.parse_cursor(payload)[0]['remainingPercent'],100)
    def test_connection_success_has_explicit_no_allowance_message(self):
        with patch.object(E,'read_app_value',return_value=('synthetic',1)),patch.object(E,'cursor_cookie',return_value='synthetic-session'),patch.object(E,'request_json',return_value=self.payload()):
            result=E.collect_cursor()
        self.assertEqual(result['status'],'unsupported')
        self.assertEqual(result['windows'],[])
        self.assertIn('官方套餐上限为 0',result['message'])
        self.assertEqual(result['plan'],'free')
    def test_zero_capacity_blocks_pre_fix_full_cache(self):
        with tempfile.TemporaryDirectory() as folder:
            gates=GateBook(Path(folder)/'gates.json',clock=time.time,jitter=lambda _:0)
            old=E.checked_result('cursor','Cursor','synthetic old contract',[window('cursor-monthly','month',remaining_percent=100)])
            state={'cursor':{'generation':'same','region':'cn','lastGood':old,'status':'ok'}}
            current=E.checked_result('cursor','Cursor','synthetic corrected contract',[])
            with patch.object(monitor,'generation',return_value='same'),patch.object(monitor,'collect_cursor',return_value=current):
                first,record=monitor.collect_one('cursor','cn',old,state,gates=gates)
                second,_=monitor.collect_one('cursor','cn',old,{'cursor':record},gates=gates)
            self.assertEqual(first['status'],'unsupported')
            self.assertTrue(record['authBlocked'])
            self.assertEqual(second['windows'],[])
