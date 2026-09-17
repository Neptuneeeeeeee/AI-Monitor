"""Last successful measured quota. Copy data without changing its timestamp."""
from copy import deepcopy
from core import number

TRANSIENT = {'network_error', 'rate_limited', 'unavailable', 'permission_required', 'error'}

def measured(value):
    return isinstance(value, dict) and number(value.get('fetchedAt')) is not None and bool(value.get('windows')) and value.get('status') in ('ok', 'partial', 'stale')

def choose(record, previous=None):
    values = [v for v in [record.get('lastGood'), record.get('result'), previous] if measured(v)]
    return deepcopy(max(values, key=lambda x:x['fetchedAt'])) if values else None

def historical(old, status, message, same=False):
    value = deepcopy(old)
    value.update(status='stale', liveStatus=status, message=message, historical=not same)
    value['note'] = '上次成功读数，非实时。' + ('当前账号尚未重新验证。' if not same else '')
    return value

def update_record(previous, value, generation=None, region='cn', success=False, error_status=None):
    record = dict(previous)
    good = choose(previous)
    if success and value.get('status') in ('ok','partial') and measured(value):
        good = deepcopy(value)
        good.pop('historical',None); good.pop('liveStatus',None)
        record['authBlocked'] = False
    if error_status == 'auth_required' or (success and value.get('status') == 'unsupported'): record['authBlocked'] = True
    record.update(generation=generation, region=region, result=value, lastAttempt=value.get('attemptedAt'), status=error_status or value.get('status'), message=value.get('message',''))
    if good: record['lastGood'] = good
    return record
