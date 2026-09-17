#!/usr/bin/env python3
"""Verify bundle identities and safe self-tests. No live credential reads."""
import argparse
import hashlib
import json
from pathlib import Path
import plistlib
import subprocess
import sys

def call(args,ok=0):
    result=subprocess.run(list(map(str,args)),capture_output=True,text=True,timeout=60)
    if result.returncode!=ok:raise ValueError('Command failed: '+str(args[0])+' '+str(args[1:])+'\n'+result.stderr[-2500:])
    return result.stdout.strip()

def verify(app:Path,channel:str)->dict:
    expected='com.thalnova.aimonitor'+('.local' if channel=='local' else '')
    info=plistlib.loads((app/'Contents/Info.plist').read_bytes());r=app/'Contents/Resources'
    profile=json.loads((r/'RuntimeProfile.json').read_text())
    if info['CFBundleIdentifier']!=expected or profile['bundleID']!=expected or profile['channel']!=channel:raise ValueError('Cross-edition app/profile')
    if profile!=json.loads((r/'collector/runtime.json').read_text()):raise ValueError('Swift/Python profile drift')
    if channel=='public' and profile['experimentalModules']:raise ValueError('Private experiments in public bundle')
    permitted={'RuntimeProfile.json','collector','BrandAssets','AppIcon.icns','AuthBridge','APIVault','Python','Distribution.json','Notices'}
    if {f.name for f in r.iterdir()}-permitted:raise ValueError('Unexpected top-level resource')
    for f in app.rglob('*'):
        if f.is_symlink():raise ValueError('Unexpected symlink in candidate')
        public_ca = f == r/'Python/certificates/cacert.pem'
        if f.name in {'.env','.git','accounts.json','snapshot.json','backups','logs','Experimental'} or f.suffix in {'.key','.pyc'} or (f.suffix=='.pem' and not public_ca):raise ValueError('Private/runtime artifact in app: '+f.name)
        if public_ca and (b'PRIVATE KEY' in f.read_bytes() or b'BEGIN CERTIFICATE' not in f.read_bytes()):raise ValueError('Invalid public certificate bundle')
    call(['/usr/bin/codesign','--verify','--deep','--strict',app])
    executable=app/'Contents/MacOS'/info['CFBundleExecutable']
    runtime=json.loads(call([executable,'--runtime-info']))
    if runtime['bundleID']!=expected or runtime['keychainPrefix']!=expected+'.' or runtime['defaultEnabledProviders']!=[]:raise ValueError('Wrong runtime/defaults')
    if runtime['pythonBundled']:
        smoke=json.loads(call([executable,'--self-test-runtime']))
        if not smoke.get('passed') or smoke.get('systemPythonUsed') is not False:raise ValueError('Bundled runtime failed its native launch test')
    helpers=[]
    for sub,label,exe,suffix in [('AuthBridge','Keychain','MonitorKeychain','.Keychain.v1'),('APIVault','API Vault','MonitorAPIVault','.APIVault.v1')]:
        folder=r/sub;bundle=folder/(profile['displayName']+' '+label+'.app');binary=bundle/'Contents/MacOS'/exe
        metadata=json.loads((folder/'identity.json').read_text());helper_info=plistlib.loads((bundle/'Contents/Info.plist').read_bytes())
        if metadata.get('bundleID')!=expected+suffix or metadata.get('channel')!=channel or helper_info['CFBundleIdentifier']!=expected+suffix:raise ValueError('Wrong helper identity')
        if metadata['binarySHA256']!=hashlib.sha256(binary.read_bytes()).hexdigest():raise ValueError('Helper hash mismatch')
        if call([binary,'--identity'])!=expected+suffix+'|'+expected+'.':raise ValueError('Wrong compiled keychain namespace')
        if sub=='AuthBridge':
            rejected=json.loads(call([binary,'--status','local.thalnova.Monitor.kimi'],ok=4))
            if rejected.get('status')!=-50:raise ValueError('Legacy namespace not rejected')
        helpers.append(expected+suffix)
    result=json.loads(call([executable,'--self-test-isolation']))
    if result.get('passed') is not True:raise ValueError('Isolation self-test failed')
    if Path(result['temporaryRoot']).exists():raise ValueError('Self-test did not remove temporary data')
    if channel=='public':
        symbols=call(['/usr/bin/nm','-j',executable])
        if 'LocalExperiments' in symbols:raise ValueError('Private module linked into public executable')
        call([executable,'--experimental-status'],ok=1)
    else:
        experiments=json.loads(call([executable,'--experimental-status']))
        if experiments.get('module')!='LocalExperiments':raise ValueError('Local extension missing')
    report={'passed':True,'channel':channel,'bundleID':expected,'helpers':helpers,'isolatedSelfTest':result,
            'publicHasNoPrivateModule':channel=='public','systemPermissionChanges':False}
    print(json.dumps(report,indent=2));return report

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('app',type=Path);p.add_argument('--channel',choices=['public','local'],required=True);a=p.parse_args()
    try:verify(a.app.resolve(),a.channel)
    except (ValueError,OSError,subprocess.SubprocessError) as error:print('BUNDLE_VERIFY_FAILED',error,file=sys.stderr);raise SystemExit(1)
