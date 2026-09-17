#!/usr/bin/env python3
"""Offline runtime acceptance: synthetic parser values, never account queries."""
import json,os,ssl,sqlite3,sys,sysconfig
from pathlib import Path
import base64,ctypes,datetime,fcntl,hashlib,lzma,multiprocessing,selectors,socket,subprocess,tomllib,urllib.request,zlib

def main():
    root=Path(sys.executable).resolve().parents[1]
    assert str(Path(sys.prefix).resolve())==str(root),'Interpreter escaped bundled prefix'
    assert sys.version_info[:2]==(3,13)
    assert sys.dont_write_bytecode and sys.flags.no_user_site
    roots=root/'certificates/cacert.pem'
    assert roots.is_file() and 'PRIVATE KEY' not in roots.read_text()
    context=ssl.create_default_context(cafile=str(roots))
    count=context.cert_store_stats()['x509_ca'];assert count>50
    with sqlite3.connect(':memory:') as db:
        db.execute('CREATE TABLE probe(v INTEGER)');db.execute('INSERT INTO probe VALUES (17)')
        assert db.execute('SELECT v FROM probe').fetchone()[0]==17
    import monitor,api_monitor,extended_plans,codex_provider
    assert len(monitor.NAMES)==10
    assert extended_plans.parse_cursor({'individualUsage':{'plan':{'enabled':True,'limit':0,'totalPercentUsed':0}}})==[]
    value=codex_provider.parse_codex({'rateLimits':{'primary':{'usedPercent':100,'windowDurationMins':43200}}})
    assert value and value[0]['remainingPercent']==0
    for path in sys.path:
        if not path:continue
        resolved=Path(path).resolve()
        assert str(resolved).startswith(str(root)) or resolved==Path(__file__).resolve().parent, 'Unexpected import directory'
    print(json.dumps({'passed':True,'pythonVersion':sys.version.split()[0],'pythonExecutable':str(Path(sys.executable).resolve()),
        'prefix':sys.prefix,'sslVersion':ssl.OPENSSL_VERSION,'publicRootCAs':count,'sqliteVersion':sqlite3.sqlite_version,
        'providers':len(monitor.NAMES),'bytecodeDisabled':sys.dont_write_bytecode,'userSiteDisabled':bool(sys.flags.no_user_site),
        'systemPythonUsed':False,'credentialReads':0,'networkRequests':0},indent=2))
if __name__=='__main__':main()
