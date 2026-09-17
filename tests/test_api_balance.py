"""API billing regression fixtures are synthetic. No real keys or network calls."""
import copy
import datetime as dt
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch,Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'collector'))
from core import MonitorError
import api_providers as P
from api_monitor import QueryState,collect_one,context,validate_account

NOW=1788762000
DAY,START,END=P.utc_day(NOW)
def account(pid='deepseek',number=1):
 return {'id':'00000000-0000-0000-0000-%012d'%number,'provider':pid,'region':'cn','currency':'CNY' if pid in ('deepseek','kimi','siliconflow') else 'USD','mode':'admin' if pid in ('openai','claude') else 'key','enabled':True,'projectID':'','credentialRevision':'synthetic-revision'}
def bucket(pid,value):
 if pid=='openai':return {'start_time':START,'end_time':END,'results':[{'amount':{'value':value,'currency':'usd'}}]}
 iso=lambda t:dt.datetime.fromtimestamp(t,dt.timezone.utc).isoformat().replace('+00:00','Z')
 return {'starting_at':iso(START),'ending_at':iso(END),'results':[{'amount':str(value),'currency':'USD'}]}

class APIParsingTests(unittest.TestCase):
 def test_seven_providers(self):self.assertEqual(len(P.PROVIDERS),7)
 def test_deepseek_actual_currency(self):
  d=P.parse_balance('deepseek',{'balance_infos':[{'currency':'CNY','total_balance':'100.01'},{'currency':'USD','total_balance':'9'}]},'CNY')
  self.assertEqual(d['balance'],100.01);self.assertNotIn('dailySpent',d)
 def test_deepseek_zero_valid(self):self.assertEqual(P.parse_balance('deepseek',{'balance_infos':[{'currency':'CNY','total_balance':'0'}]},'CNY')['balance'],0)
 def test_deepseek_does_not_mix_currency(self):
  with self.assertRaises(MonitorError):P.parse_balance('deepseek',{'balance_infos':[{'currency':'USD','total_balance':'9'}]},'CNY')
 def test_missing_not_zero(self):
  with self.assertRaises(MonitorError):P.parse_balance('deepseek',{'balance_infos':[{'currency':'CNY'}]},'CNY')
 def test_kimi_uses_available_not_sum(self):
  self.assertEqual(P.parse_balance('kimi',{'data':{'available_balance':3,'cash_balance':-10,'voucher_balance':3}},'CNY')['balance'],3)
 def test_siliconflow_total(self):self.assertEqual(P.parse_balance('siliconflow',{'data':{'totalBalance':'88.88','balance':'0.88','chargeBalance':'88'}},'USD')['balance'],88.88)
 def test_provider_failure_not_valid(self):
  with self.assertRaises(MonitorError):P.parse_balance('kimi',{'status':False,'data':{'available_balance':100}},'CNY')
 def test_invalid_numbers(self):
  for x in ['NaN','Infinity',True,{},None]:self.assertIsNone(P.amount(x))
 def test_router_key_no_wallet(self):
  r=P.parse_openrouter({'data':{'limit':10,'limit_remaining':7,'usage_daily':2,'limit_reset':'monthly'}},'key')
  self.assertEqual(r['dailySpent'],2);self.assertEqual(r['balanceLabel'],'Key 剩余额度');self.assertEqual(r['limitPeriod'],'每月')
 def test_router_no_limit_not_zero(self):
  r=P.parse_openrouter({'data':{'limit':None,'limit_remaining':None,'usage_daily':0}},'key');self.assertIsNone(r['balance']);self.assertEqual(r['dailySpent'],0)
 def test_router_management_no_daily(self):
  r=P.parse_openrouter({'data':{'total_credits':100,'total_usage':30}},'management');self.assertEqual(r['balance'],70);self.assertNotIn('dailySpent',r)
 def test_router_missing_management_fields(self):
  with self.assertRaises(MonitorError):P.parse_openrouter({'data':{'total_credits':100}},'management')
 def test_openai_major_units(self):self.assertEqual(P.parse_cost_pages('openai',[{'data':[bucket('openai',12.34)]}],START,END),12.34)
 def test_claude_fractional_cents(self):self.assertAlmostEqual(P.parse_cost_pages('claude',[{'data':[bucket('claude','123.78912')]}],START,END),1.2378912)
 def test_decimal_sum(self):self.assertEqual(P.parse_cost_pages('openai',[{'data':[bucket('openai',0.1),bucket('openai',0.2)]}],START,END),0.3)
 def test_absent_current_day_unknown(self):self.assertIsNone(P.parse_cost_pages('openai',[{'data':[]}],START,END))
 def test_empty_known_bucket_zero(self):
  b=bucket('openai',0);b['results']=[];self.assertEqual(P.parse_cost_pages('openai',[{'data':[b]}],START,END),0)
 def test_previous_day_rejected(self):
  b=bucket('openai',1);b['start_time']=START-86400
  with self.assertRaises(MonitorError):P.parse_cost_pages('openai',[{'data':[b]}],START,END)
 def test_unknown_cost_not_partial_sum(self):
  b=bucket('openai',None)
  with self.assertRaises(MonitorError):P.parse_cost_pages('openai',[{'data':[b]}],START,END)
 def test_foreign_cost_currency_not_summed(self):
  b=bucket('openai',1);b['results'][0]['amount']['currency']='eur'
  with self.assertRaises(MonitorError):P.parse_cost_pages('openai',[{'data':[b]}],START,END)
 def test_claude_workspace_scope(self):
  b=bucket('claude',100);b['results'][0]['workspace_id']='one';b['results'].append({'workspace_id':'two','amount':'500','currency':'USD'})
  self.assertEqual(P.parse_cost_pages('claude',[{'data':[b]}],START,END,'one'),1)
 def test_pagination_reads_all(self):
  f=Mock(side_effect=[{'data':[bucket('openai',2)],'has_more':True,'next_page':'next'},{'data':[bucket('openai',3)],'has_more':False}])
  self.assertEqual(P.collect(account('openai'),'synthetic',fetch=f,now=NOW)['dailySpent'],5);self.assertEqual(f.call_count,2)
 def test_missing_pagination_flag_not_zero(self):
  with self.assertRaises(MonitorError):P.collect(account('openai'),'synthetic',fetch=lambda *x:{'data':[]},now=NOW)
 def test_pagination_cycle_rejected(self):
  with self.assertRaises(MonitorError):P.collect(account('claude'),'synthetic',fetch=lambda *x:{'data':[],'has_more':True,'next_page':'same'},now=NOW)
 def test_google_validation_not_money(self):
  r=P.collect(account('google'),'synthetic',fetch=lambda *x:{'models':[{'name':'synthetic'}]},now=NOW)
  self.assertEqual(r['status'],'unsupported');self.assertNotIn('balance',r);self.assertNotIn('dailySpent',r)
 def test_google_does_not_generate(self):
  a=account('google');self.assertTrue(P.route(a)[0].endswith('/models'))
 def test_region_changes_endpoint(self):
  a=account('siliconflow');self.assertIn('siliconflow.cn',P.route(a)[0]);a['region']='global';self.assertIn('siliconflow.com',P.route(a)[0])
 def test_scope_params_no_keys(self):
  a=account('openai');a['projectID']='proj_one';f=Mock(return_value={'data':[bucket('openai',1)],'has_more':False});P.collect(a,'synthetic',fetch=f,now=NOW)
  self.assertEqual(f.call_args[0][2]['project_ids'],['proj_one']);self.assertNotIn('synthetic',str(f.call_args[0][2]))
 def test_no_unauthorized_params(self):
  with self.assertRaises(MonitorError):P.get(account(),'synthetic',{'api_key':'secret'})
 def test_newline_key_rejected(self):
  with self.assertRaises(MonitorError):P.get(account(),'abc\nInjected: bad')
 def test_redirect_denied(self):
  with self.assertRaises(MonitorError):P.NoRedirect().redirect_request(None,None,302,'',{},'https://other.invalid')
 def test_context_excludes_budget(self):
  a=account();b=dict(a,dailyBudget=100);self.assertEqual(context(a),context(b))
 def test_context_rotates_with_key(self):self.assertNotEqual(context(account()),context(dict(account(),credentialRevision='new')))
 def test_extra_secret_not_in_config(self):
  a=account();a['api_key']='synthetic';self.assertNotIn('api_key',validate_account(a))
 def test_bad_identifier(self):
  with self.assertRaises(ValueError):validate_account(dict(account(),id='../../escape'))

class APIGateTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.now=NOW
  self.state=QueryState(self.temp.name,clock=lambda:self.now,jitter=lambda:0);self.calls=0
 def adapter(self,a,key):
  self.calls+=1;return {'status':'ok','currency':'CNY','balance':100,'dailySpent':None,'fetchedAt':self.now,'source':'synthetic','message':''}
 def test_no_key_no_network(self):
  r=collect_one(dict(account(),credentialRevision=''),self.state,{},key_reader=Mock(side_effect=AssertionError),adapter=Mock(side_effect=AssertionError))
  self.assertEqual(r['status'],'not_configured');self.assertEqual(self.state.gates,{})
 def test_disabled_no_network(self):
  r=collect_one(dict(account(),enabled=False),self.state,{},key_reader=Mock(side_effect=AssertionError));self.assertEqual(r['status'],'disabled')
 def test_burst_one_provider_call(self):
  a=account();cache={}
  for _ in range(30):cache[a['id']]=collect_one(a,self.state,cache,key_reader=lambda _: 'synthetic',adapter=self.adapter)
  self.assertEqual(self.calls,1);self.assertEqual(cache[a['id']]['balance'],100)
 def test_restart_preserves_deadline(self):
  a=account();self.state.reserve(a);new=QueryState(self.temp.name,clock=lambda:self.now,jitter=lambda:0);self.assertFalse(new.reserve(a)[0])
 def test_key_change_does_not_bypass_rate_gate(self):
  a=account();self.state.reserve(a);self.state.finish(a,MonitorError('rate_limited','fixture',retry_after=4000));a['credentialRevision']='other';self.assertFalse(self.state.reserve(a)[0])
 def test_provider_limit_blocks_sibling_key(self):
  a=account();self.state.reserve(a);self.state.finish(a,MonitorError('rate_limited','fixture'));self.assertFalse(self.state.reserve(account(number=2))[0])
 def test_other_provider_unaffected(self):
  a=account();self.state.reserve(a);self.state.finish(a,MonitorError('rate_limited','fixture'));self.assertTrue(self.state.reserve(account('kimi',2))[0])
 def test_cache_stays_measured_after_network_error(self):
  a=account();r=collect_one(a,self.state,{},key_reader=lambda _: 'synthetic',adapter=self.adapter);self.now+=1000
  with patch('api_monitor.collect'):n=collect_one(a,self.state,{a['id']:r},key_reader=lambda _:'synthetic',adapter=Mock(side_effect=MonitorError('network_error','fixture')))
  self.assertEqual(n['status'],'stale');self.assertEqual(n['fetchedAt'],NOW);self.assertEqual(n['balance'],100)
 def test_auth_rejection_does_not_keep_old_balance(self):
  a=account();r=collect_one(a,self.state,{},key_reader=lambda _:'synthetic',adapter=self.adapter);self.now+=1000
  n=collect_one(a,self.state,{a['id']:r},key_reader=lambda _:'synthetic',adapter=Mock(side_effect=MonitorError('auth_required','fixture')))
  self.assertNotIn('balance',n)
 def test_changed_account_does_not_show_old_wallet(self):
  a=account();r=collect_one(a,self.state,{},key_reader=lambda _:'synthetic',adapter=self.adapter);a['credentialRevision']='new'
  n=collect_one(a,self.state,{a['id']:r},key_reader=Mock(side_effect=AssertionError));self.assertNotIn('balance',n)
 def test_query_before_gate_is_persisted(self):
  a=account()
  def check(a,key):self.assertTrue((Path(self.temp.name)/'gates.json').exists());return self.adapter(a,key)
  collect_one(a,self.state,{},key_reader=lambda _:'synthetic',adapter=check)
 def test_server_wait_not_capped(self):
  a=account();self.state.reserve(a);deadline=self.state.finish(a,MonitorError('rate_limited','fixture',retry_after=20000));self.assertGreaterEqual(deadline,self.now+20000)

if __name__=='__main__':unittest.main(verbosity=2)
