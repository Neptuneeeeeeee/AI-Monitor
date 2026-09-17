#!/usr/bin/env python3
"""One bounded API balance round, fully separate from Coding Plan caches/gates."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from copy import deepcopy
import fcntl
import hashlib
import json
import os
from pathlib import Path
import random
import re
import signal
import sys
import threading
import time
from core import SUPPORT, MonitorError, atomic_json, read_json, run
from api_providers import PROVIDERS, collect, utc_day
from monitor import shutdown

ROOT=SUPPORT/'API'
SAFE_FIELDS={'id','provider','alias','enabled','region','currency','dailyBudget','balanceReference','mode','projectID','credentialRevision'}
PUBLIC={'id','context','status','currency','balance','balanceLabel','dailySpent','dayUTC','keyLimit','limitPeriod','fetchedAt','nextQueryAt','source','message'}

def validate_account(a):
    if not isinstance(a,dict) or a.get('provider') not in PROVIDERS: raise ValueError('unknown API account')
    if not re.fullmatch(r'[0-9a-fA-F-]{36}',a.get('id','')): raise ValueError('invalid account id')
    if a.get('region') not in ('cn','global') or a.get('currency') not in ('CNY','USD'): raise ValueError('invalid region/currency')
    if a.get('mode') not in ('key','admin','management'): raise ValueError('invalid mode')
    if not isinstance(a.get('credentialRevision',''),str) or len(a.get('credentialRevision',''))>80: raise ValueError('invalid revision')
    if not re.fullmatch(r'[A-Za-z0-9_-]{0,120}',a.get('projectID','')): raise ValueError('invalid project ID')
    return {k:a[k] for k in SAFE_FIELDS if k in a}

def context(a):
    currency=('CNY' if a.get('region')=='cn' else 'USD') if a['provider'] in ('kimi','siliconflow') else (a.get('currency','USD') if a['provider']=='deepseek' else 'USD')
    return '|'.join([a['provider'],a.get('region','cn'),a.get('mode','key'),a.get('projectID',''),currency,a.get('credentialRevision','')])

def placeholder(a,status,message):
    return {'id':a['id'],'context':context(a),'status':status,'currency':context(a).split('|')[-2],'source':'','message':message}

def read_key(account_id):
    helper=os.environ.get('MONITOR_API_VAULT')
    if not helper: raise MonitorError('unavailable','API 钥匙串组件未就绪，请重开应用。')
    rc,out=run([helper,'--read',account_id],timeout=15)
    if rc==2: raise MonitorError('auth_required','未找到已保存的 Key，请在 API 账户设置中重新保存。')
    if rc==3: raise MonitorError('permission_required','API 钥匙串已锁定或需要授权，请在账户设置中保存/授权固定组件。')
    if rc: raise MonitorError('unavailable','API 钥匙串暂不可用；没有请求服务商。')
    return out.decode('utf-8')

class QueryState:
    def __init__(self,root,clock=time.time,jitter=None):
        self.root=Path(root);self.clock=clock;self.jitter=jitter or (lambda:random.uniform(0,40));self.lock=threading.Lock()
        doc=read_json(self.root/'gates.json',{})
        self.gates=doc if isinstance(doc,dict) else {}
    def reserve(self,a):
        with self.lock:
            now=self.clock();pid=a['provider'];aid=a['id']; old=dict(self.gates.get(aid) or {})
            provider_deadline=(self.gates.get('provider:'+pid) or {}).get('next',0)
            deadline=max(old.get('next',0),provider_deadline)
            if deadline>now: return False,deadline,old
            interval=3600 if pid=='google' else 1800 if pid in ('claude','openai') else 900
            old.update(next=now+interval,last=now,count=int(old.get('count',0))+1,interval=interval)
            self.gates[aid]=old;atomic_json(self.root/'gates.json',self.gates)
            return True,old['next'],old
    def finish(self,a,error=None):
        with self.lock:
            old=dict(self.gates.get(a['id']) or {});now=self.clock();interval=old.get('interval',900)
            if error:
                failures=min(10,old.get('failures',0)+1)
                delay=max(interval,min(7200,900*2**(failures-1)),error.retry_after or 0)
                old.update(next=now+delay+self.jitter(),failures=failures,status=error.status)
                if error.status=='rate_limited': self.gates['provider:'+a['provider']]={'next':old['next']}
            else: old.update(next=now+interval+self.jitter(),failures=0,status='ok')
            self.gates[a['id']]=old;atomic_json(self.root/'gates.json',self.gates)
            return old['next']

def collect_one(a,state,cache,key_reader=read_key,adapter=collect):
    if not a.get('enabled',True): return placeholder(a,'disabled','此账户已暂停查询。')
    if not a.get('credentialRevision'): return placeholder(a,'not_configured','在 API 设置中添加 Key。')
    cached=cache.get(a['id'])
    if not isinstance(cached,dict) or cached.get('context')!=context(a): cached=None
    allowed,next_at,gate=state.reserve(a)
    if not allowed:
        out=deepcopy(cached) if cached else placeholder(a,'rate_limited' if gate.get('status')=='rate_limited' else 'unavailable','已安排查询，等待当前冷却结束。')
        out['nextQueryAt']=next_at
        return out
    try:
        key=key_reader(a['id'])
        out=adapter(a,key)
        # Key is not returned, included in a cache key, or written to the logs.
        out.update(id=a['id'],context=context(a),nextQueryAt=state.finish(a))
        return {k:v for k,v in out.items() if k in PUBLIC}
    except MonitorError as error: pass_error=error
    except Exception as error: pass_error=MonitorError('error','API 适配器未完成（'+type(error).__name__+'），未推算金额。')
    next_at=state.finish(a,pass_error)
    if cached and pass_error.status in ('rate_limited','network_error','unavailable') and cached.get('fetchedAt'):
        out=deepcopy(cached);out.update(status='stale',message=pass_error.message+' 显示最后成功读数。',nextQueryAt=next_at)
    else: out=placeholder(a,pass_error.status,pass_error.message);out['nextQueryAt']=next_at
    return out

def main():
    ROOT.mkdir(parents=True,exist_ok=True,mode=0o700);os.chmod(ROOT,0o700)
    lock=open(ROOT/'collection.lock','a');os.chmod(ROOT/'collection.lock',0o600)
    try: fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError: return 75
    # A bounded observer-friendly one-shot process; no work outlives the parent.
    for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGALRM): signal.signal(sig,shutdown)
    signal.alarm(115)
    config=read_json(ROOT/'accounts.json',[])
    if not isinstance(config,list) or len(config)>28: return 65
    accounts=[validate_account(a) for a in config]
    if len({a['id'] for a in accounts})!=len(accounts): return 65
    state=QueryState(ROOT); cache=read_json(ROOT/'cache.json',{})
    if not isinstance(cache,dict): cache={}
    results={}
    with ThreadPoolExecutor(max_workers=2,thread_name_prefix='api-billing') as pool:
        futures={pool.submit(collect_one,a,state,cache):a['id'] for a in accounts}
        for future in as_completed(futures):
            aid=futures[future];result=future.result();results[aid]=result
            cache[aid]=result;atomic_json(ROOT/'cache.json',cache)
    snapshot={'schemaVersion':1,'generatedAt':time.time(),'accounts':[results[a['id']] for a in accounts]}
    atomic_json(ROOT/'snapshot.json',snapshot)
    print(json.dumps(snapshot,ensure_ascii=False,allow_nan=False,separators=(',',':')))
    signal.alarm(0);fcntl.flock(lock,fcntl.LOCK_UN);lock.close()
    return 0

if __name__=='__main__':
    try: sys.exit(main())
    except Exception as error:
        # Never include exception contents or a provider response in stderr.
        print('API collection failed: '+type(error).__name__,file=sys.stderr);sys.exit(1)
