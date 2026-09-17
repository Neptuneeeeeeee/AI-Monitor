"""Read-only, first-party API balance/cost adapters. Never call a model.
Docs and capability boundaries are recorded in docs/API_BALANCE_1_6.md.
"""
import datetime as dt
from decimal import Decimal, InvalidOperation
import json
import socket
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from core import MonitorError
from rate_limits import http_error, has_rate_signal

PROVIDERS = ('deepseek','kimi','openai','claude','siliconflow','openrouter','google')
ROUTES = {
    ('deepseek','cn','key'): ('https://api.deepseek.com/user/balance', set()),
    ('kimi','cn','key'): ('https://api.moonshot.cn/v1/users/me/balance', set()),
    ('kimi','global','key'): ('https://api.moonshot.ai/v1/users/me/balance', set()),
    ('siliconflow','cn','key'): ('https://api.siliconflow.cn/v1/user/info', set()),
    ('siliconflow','global','key'): ('https://api.siliconflow.com/v1/user/info', set()),
    ('openai','cn','admin'): ('https://api.openai.com/v1/organization/costs', {'start_time','end_time','bucket_width','limit','page','project_ids'}),
    ('claude','cn','admin'): ('https://api.anthropic.com/v1/organizations/cost_report', {'starting_at','ending_at','bucket_width','limit','page','group_by[]'}),
    ('openrouter','cn','key'): ('https://openrouter.ai/api/v1/key', set()),
    ('openrouter','cn','management'): ('https://openrouter.ai/api/v1/credits', set()),
    ('google','cn','key'): ('https://generativelanguage.googleapis.com/v1beta/models', {'pageSize'}),
}

def decimal(value):
    if value is None or isinstance(value,bool): return None
    try:
        d = Decimal(str(value))
        return d if d.is_finite() and abs(d) <= Decimal('1e15') else None
    except (InvalidOperation,ValueError,TypeError): return None

def amount(value, required=False):
    v = decimal(value)
    if required and v is None: raise MonitorError('error','账单响应缺少金额，未将未知值当成零。')
    return float(v) if v is not None else None

def utc_day(now=None):
    d = dt.datetime.fromtimestamp(time.time() if now is None else now,dt.timezone.utc)
    start = d.replace(hour=0,minute=0,second=0,microsecond=0)
    return start.strftime('%Y-%m-%d'), int(start.timestamp()), int((start+dt.timedelta(days=1)).timestamp())

def route(account):
    pid=account['provider']; region=account.get('region','cn') if pid in ('kimi','siliconflow') else 'cn'
    mode=account.get('mode','key') if pid in ('openai','claude','openrouter') else 'key'
    value=ROUTES.get((pid,region,mode))
    if not value: raise MonitorError('unsupported','所选认证方式不支持此官方查询接口。')
    return value

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        raise MonitorError('error','官方接口发生重定向，已阻止转发 API Key。')

def get(account,key,params=None):
    base, allowed = route(account); params=params or {}
    if set(params)-allowed: raise MonitorError('error','拒绝未授权的查询参数。')
    if not isinstance(key,str) or not key or len(key)>8192 or any(ord(c)<33 or ord(c)>126 for c in key):
        raise MonitorError('auth_required','Key 格式不正确，请重新输入。')
    url=base + ('?'+urllib.parse.urlencode(params,doseq=True) if params else '')
    headers={'Accept':'application/json','User-Agent':'Monitor/1.6 (read-only API billing)'}
    if account['provider']=='claude': headers.update({'x-api-key':key,'anthropic-version':'2023-06-01'})
    elif account['provider']=='google': headers['x-goog-api-key']=key
    else: headers['Authorization']='Bearer '+key
    opener=urllib.request.build_opener(NoRedirect(),urllib.request.HTTPSHandler(context=ssl.create_default_context()))
    try:
        with opener.open(urllib.request.Request(url,headers=headers,method='GET'),timeout=12) as r:
            raw=r.read(2*1024*1024+1)
            if len(raw)>2*1024*1024: raise MonitorError('error','账单响应过大，未展示不完整金额。')
            obj=json.loads(raw)
            if not isinstance(obj,dict): raise MonitorError('error','无法识别官方账单结构。')
            if has_rate_signal(obj): raise http_error(429,r.headers,obj)
            return obj
    except urllib.error.HTTPError as e:
        try: payload=json.loads(e.read(32768))
        except Exception: payload={}
        err=http_error(e.code,e.headers,payload)
        if e.code==401: err.message='服务商拒绝 API Key，请检查所属平台、区域和 Key 类型。'
        if e.code==403 and err.status!='rate_limited': err.message='当前凭证无账单访问权限；不能据此判断模型调用 Key 已失效。'
        raise err
    except (urllib.error.URLError,TimeoutError,socket.timeout,ssl.SSLError,ConnectionError):
        raise MonitorError('network_error','账单连接暂不可用，保留上次成功金额。')
    except (ValueError,UnicodeDecodeError): raise MonitorError('error','账单接口未返回有效 JSON。')

def parse_balance(pid,payload,currency):
    if pid=='deepseek':
        rows=payload.get('balance_infos')
        if not isinstance(rows,list): raise MonitorError('error','未返回余额列表。')
        row=next((r for r in rows if isinstance(r,dict) and r.get('currency')==currency),None)
        if row is None: raise MonitorError('unsupported','接口没有返回所选币种的余额；没有合并不同币种。')
        value=amount(row.get('total_balance'),True)
    else:
        if payload.get('status') is False: raise MonitorError('permission_required','官方余额查询未通过，请检查平台与 Key。')
        data=payload.get('data')
        if not isinstance(data,dict): raise MonitorError('error','未返回账户余额。')
        value=amount(data.get('available_balance' if pid=='kimi' else 'totalBalance'),True)
    return {'balance':value,'balanceLabel':'账户余额','message':'此余额接口未提供今日消费；余额差值不会当成消费。'}

def parse_openrouter(payload,mode):
    data=payload.get('data')
    if not isinstance(data,dict): raise MonitorError('error','未返回 OpenRouter Key / 账户信息。')
    if mode=='management':
        credits=decimal(data.get('total_credits'));used=decimal(data.get('total_usage'))
        if credits is None or used is None: raise MonitorError('error','账户充值/消费总额缺失，不能计算余额。')
        return {'balance':float(credits-used),'balanceLabel':'账户余额','message':'Management Key 查询账户余额，不提供此账户今日合计费用。'}
    period={'daily':'每日','weekly':'每周','monthly':'每月'}.get(data.get('limit_reset'),'累计')
    out={'dailySpent':amount(data.get('usage_daily')),'balance':amount(data.get('limit_remaining')),
         'balanceLabel':'Key 剩余额度','keyLimit':amount(data.get('limit')),'limitPeriod':period,
         'message':'今日费用是当前 Key 的 OpenRouter 费用，不是账户余额；BYOK 提供商费用单独计费。'}
    if data.get('include_byok_in_limit'): out['message']+=' 该 Key 上限还包括 BYOK 用量，和今日 OpenRouter 费用口径不同。'
    if out['balance'] is None and out['dailySpent'] is None: raise MonitorError('unsupported','该 Key 未返回可量化余额或今日费用。')
    return out

def parse_cost_pages(pid,pages,start,end,project=''):
    total=Decimal(0); bucket_seen=False
    for page in pages:
        if not isinstance(page.get('data'),list): raise MonitorError('error','费用列表缺失。')
        for bucket in page['data']:
            if not isinstance(bucket,dict): raise MonitorError('error','费用时间桶结构变化。')
            if pid=='openai': begin=bucket.get('start_time');finish=bucket.get('end_time')
            else:
                try:
                    begin=dt.datetime.fromisoformat(bucket['starting_at'].replace('Z','+00:00')).timestamp()
                    finish=dt.datetime.fromisoformat(bucket['ending_at'].replace('Z','+00:00')).timestamp()
                except (ValueError,KeyError,AttributeError): raise MonitorError('error','费用时间范围无法确认。')
            if begin!=start or finish!=end: raise MonitorError('error','服务商返回的时间桶不匹配今日 UTC，未拼接成今日费用。')
            bucket_seen=True
            rows=bucket.get('results')
            if not isinstance(rows,list): raise MonitorError('error','费用明细缺失。')
            for row in rows:
                if project and pid=='claude' and row.get('workspace_id')!=project: continue
                m=row.get('amount')
                currency=(m.get('currency') if isinstance(m,dict) else row.get('currency'))
                if str(currency).upper()!='USD': raise MonitorError('error','费用币种不是 USD，未自动换算。')
                value=decimal(m.get('value') if pid=='openai' and isinstance(m,dict) else m)
                if value is None: raise MonitorError('error','费用明细存在未知金额，未展示不完整合计。')
                total += value if pid=='openai' else value/100
    # An absent current bucket often means reporting latency, not a proven zero.
    return float(total) if bucket_seen else None

def collect(account,key,fetch=get,now=None):
    pid=account['provider'];day,start,end=utc_day(now)
    currency=account.get('currency','USD')
    if pid in ('kimi','siliconflow'): currency='CNY' if account.get('region')=='cn' else 'USD'
    elif pid!='deepseek': currency='USD'
    result={'status':'ok','currency':currency,'dayUTC':day,'source':route(account)[0].split('?')[0],'message':''}
    if pid in ('deepseek','kimi','siliconflow'):
        result.update(parse_balance(pid,fetch(account,key),currency))
    elif pid=='openrouter': result.update(parse_openrouter(fetch(account,key),account.get('mode','key')))
    elif pid=='google':
        payload=fetch(account,key,{'pageSize':1})
        if not isinstance(payload.get('models'),list): raise MonitorError('error','未获得模型列表访问结果。')
        result.update(status='unsupported',message='Key 的模型列表访问正常；此 API 不返回余额/今日费用。请打开 AI Studio 账单查看，不能显示为免费或无限额度。')
    else:
        project=account.get('projectID','').strip()
        if pid=='openai':
            params={'start_time':start,'end_time':end,'bucket_width':'1d','limit':1}
            if project: params['project_ids']=[project]
        else:
            iso=lambda stamp:dt.datetime.fromtimestamp(stamp,dt.timezone.utc).isoformat().replace('+00:00','Z')
            params={'starting_at':iso(start),'ending_at':iso(end),'bucket_width':'1d','limit':1}
            if project: params['group_by[]']=['workspace_id']
        pages=[]; seen=set();deadline=time.monotonic()+35
        for _ in range(4):
            if time.monotonic()>deadline: raise MonitorError('network_error','账单分页超时，未展示不完整费用。')
            page=fetch(account,key,params);pages.append(page)
            if page.get('has_more') is False: break
            cursor=page.get('next_page')
            if page.get('has_more') is not True or not isinstance(cursor,str) or not cursor or cursor in seen or len(cursor)>2048:
                raise MonitorError('error','账单分页不完整，未展示部分金额。')
            seen.add(cursor);params=dict(params,page=cursor)
        else: raise MonitorError('error','账单超过单轮分页上限，未展示不完整合计。')
        result['dailySpent']=parse_cost_pages(pid,pages,start,end,project)
        scope=('项目' if pid=='openai' else '工作区') if project else '组织'
        result['message']=scope+'今日已入账费用（UTC），可能延迟；不是普通调用 Key 的钱包余额。'
        if pid=='claude': result['message']+=' 不含 Priority Tier 费用。'
        if result['dailySpent'] is None: result.update(status='partial',message='今日费用尚未入账；未将缺失时间桶显示成零。')
    result['fetchedAt']=time.time() if now is None else now
    return result
