#!/usr/bin/env python3
"""Package a tested bundled-runtime app as an explicitly unnotarized preview.

No installation, login change or GitHub write is performed by this script.
"""
from __future__ import annotations
import argparse,hashlib,json,os,plistlib,shutil,subprocess,sys,tempfile,time,zipfile
from pathlib import Path
from build import PUBLIC,output_for,source_hashes
from git_provenance import repository_state

def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for data in iter(lambda:f.read(1024*1024),b''):h.update(data)
    return h.hexdigest()
def file_hashes(root):return {str(f.relative_to(root)):sha(f) for f in sorted(root.rglob('*')) if f.is_file()}
def run(args,timeout=120,env=None,capture=False):
    print('+',' '.join(map(str,args)),flush=True)
    r=subprocess.run(list(map(str,args)),check=True,timeout=timeout,env=env,
                     stdout=subprocess.PIPE if capture else None,stderr=subprocess.PIPE if capture else None)
    return r.stdout if capture else b''
def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preview',action='store_true',help='Acknowledge this is not an Apple-notarized stable release')
    args=parser.parse_args()
    if not args.preview:raise ValueError('Use --preview; stable-release requirements remain separate')
    out=output_for(PUBLIC,'public');receipt=json.loads((out/'BUILD.json').read_text())
    app=(out/receipt['app']).resolve();version=receipt['version'];tag='v'+version
    state=repository_state(PUBLIC)
    if not receipt.get('pythonBundled') or not receipt.get('testsRun'):raise ValueError('A tested bundled-runtime build is required')
    if not state.get('available') or state.get('dirty') or state['commit']!=receipt['publicGit']['commit']:raise ValueError('Build must match clean committed source')
    if receipt['publicSourceHashes']!=source_hashes(PUBLIC) or receipt['appFileHashes']!=file_hashes(app):raise ValueError('Build/source drift')
    if receipt['architecture']!='arm64':raise ValueError('This preview is tested only on Apple Silicon')
    destination=(PUBLIC.parent/'releases'/tag if (PUBLIC.parent/'WORKSPACE.json').exists() else PUBLIC/'dist/releases'/tag)
    if destination.exists():raise ValueError('Release output already exists; review before replacing it')
    destination.mkdir(parents=True)
    report={'schema':1,'version':version,'tag':tag,'sourceCommit':state['commit'],'architecture':'arm64','minimumMacOS':'14.0',
            'notarized':False,'signing':'ad-hoc','releaseChannel':'preview','pythonBundled':True,
            'pythonVersion':receipt['runtime']['python']['version'],'runtimeArchiveSHA256':receipt['runtime']['python']['sha256'],
            'certifiVersion':receipt['runtime']['certifi']['version'],'privateAccountsBundled':False,
            'sourceLicenseSelected':False,'testedOnSecondCleanMac':False,'checks':{}}
    try:
        with tempfile.TemporaryDirectory(prefix='AI-Monitor-distribution-') as folder:
            temp=Path(folder);fresh=temp/'empty-home';fresh.mkdir()
            # Deliberately relocate away from every build/cache directory and use spaces.
            relocated=temp/'Relocated App With Spaces'/'AI Monitor.app';relocated.parent.mkdir()
            run(['/usr/bin/ditto','--norsrc','--noextattr',app,relocated])
            if file_hashes(relocated)!=receipt['appFileHashes']:raise ValueError('Relocation altered app bytes')
            run(['/usr/bin/codesign','--verify','--deep','--strict',relocated])
            env={'HOME':str(fresh),'PATH':'/usr/bin:/bin:/usr/sbin:/sbin','TMPDIR':str(temp),
                 'PYTHONHOME':'/nonexistent-system-python','PYTHONPATH':'/nonexistent-user-modules',
                 'PYTHONDONTWRITEBYTECODE':'1','PYTHONNOUSERSITE':'1'}
            exe=relocated/'Contents/MacOS/AIMonitor'
            info=json.loads(run([exe,'--runtime-info'],env=env,capture=True))
            if not info['pythonBundled'] or not info['pythonExecutable'].startswith(str(relocated)):raise ValueError('Runtime path is not inside relocated app')
            smoke=json.loads(run([exe,'--self-test-runtime'],env=env,capture=True))
            if not smoke['passed'] or smoke['systemPythonUsed']:raise ValueError('Isolated runtime failed')
            report['checks']['nativeBundledRuntime']={k:v for k,v in smoke.items() if k not in {'pythonExecutable','prefix'}}
            report['checks']['relocationWithSpaces']=True
            # CA validation against a public HTTPS page, without account cookies or keys.
            python=relocated/'Contents/Resources/Python/bin/python3'
            tls_env={k:v for k,v in env.items() if k not in {'PYTHONHOME','PYTHONPATH'}}
            tls_env['SSL_CERT_FILE']=str(relocated/'Contents/Resources/Python/certificates/cacert.pem')
            tls=json.loads(run([python,'-B','-I','-c',"import json,ssl,urllib.request; c=ssl.create_default_context(); r=urllib.request.urlopen('https://github.com/',context=c,timeout=25); print(json.dumps({'verifiedHTTPS':r.status==200,'certificateVerification':c.verify_mode==ssl.CERT_REQUIRED,'hostnameVerification':c.check_hostname}))"],env=tls_env,capture=True,timeout=40))
            if not all(tls.values()):raise ValueError('TLS validation failed')
            report['checks']['tls']=tls
            demo=temp/'demo-selftest.json'
            run([exe,'--demo','--demo-self-test','--demo-receipt',demo],env=env,timeout=90)
            demo_result=json.loads(demo.read_text())
            if demo_result['status']!='checks-passed' or demo_result['servicesEnabled'] or demo_result['apiServicesEnabled']:raise ValueError('Disconnected native preview failed')
            report['checks']['nativeDemoChecks']=demo_result['checkCount']
            ui=temp/'ui-fixture';run([exe,'--render-preview',ui],env=env,timeout=180)
            native=json.loads((ui/'ui-interaction-checks.json').read_text())
            if not native.get('passed') or native.get('skipped'):raise ValueError('Native UI acceptance failed or skipped')
            report['checks']['nativeUIChecks']=native['count']
            # A signed app must stay byte-identical after runtime and UI self-tests.
            if file_hashes(relocated)!=receipt['appFileHashes']:raise ValueError('Packaged application wrote into its bundle')
            report['checks']['noWritesIntoAppBundle']=True
            archive=destination/('AI-Monitor-'+tag+'-macos-arm64.zip')
            run(['/usr/bin/ditto','-c','-k','--norsrc','--noextattr','--keepParent',relocated,archive])
            with zipfile.ZipFile(archive) as z:
                if z.testzip() is not None:raise ValueError('ZIP CRC verification failed')
                actual={n[len('AI Monitor.app/'):]:hashlib.sha256(z.read(n)).hexdigest() for n in z.namelist() if not n.endswith('/')}
                if actual!=receipt['appFileHashes']:raise ValueError('ZIP file hashes differ')
            report['checks']['zipMatchesTestedApp']=True
            volume=temp/'volume';volume.mkdir()
            run(['/usr/bin/ditto','--norsrc','--noextattr',relocated,volume/'AI Monitor.app'])
            (volume/'Applications').symlink_to('/Applications',target_is_directory=True)
            shutil.copyfile(PUBLIC/'docs/INSTALL.md',volume/'INSTALL.txt')
            dmg=destination/('AI-Monitor-'+tag+'-macos-arm64.dmg')
            run(['/usr/bin/hdiutil','create','-volname','AI Monitor '+version,'-srcfolder',volume,'-format','UDZO','-fs','HFS+',dmg],timeout=180)
            run(['/usr/bin/hdiutil','verify',dmg],timeout=90)
            attached=plistlib.loads(run(['/usr/bin/hdiutil','attach','-readonly','-nobrowse','-plist',dmg],capture=True,timeout=90))
            mount=next(Path(x['mount-point']) for x in attached['system-entities'] if x.get('mount-point'))
            try:
                if file_hashes(mount/'AI Monitor.app')!=receipt['appFileHashes']:raise ValueError('Mounted DMG app differs')
                run(['/usr/bin/codesign','--verify','--deep','--strict',mount/'AI Monitor.app'])
                if not (mount/'Applications').is_symlink():raise ValueError('DMG install shortcut missing')
            finally:run(['/usr/bin/hdiutil','detach',mount],timeout=45)
            report['checks']['mountedDMGMatchesTestedApp']=True
        shutil.copyfile(PUBLIC/'docs/INSTALL.md',destination/'INSTALL.md')
        report['appPayloadSHA256']=hashlib.sha256(json.dumps(receipt['appFileHashes'],sort_keys=True).encode()).hexdigest()
        report['completedAt']=time.time();report['passed']=True
        (destination/'RELEASE.json').write_text(json.dumps(report,indent=2)+'\n')
        files=sorted(x for x in destination.iterdir() if x.is_file())
        (destination/'SHA256SUMS').write_text(''.join(sha(f)+'  '+f.name+'\n' for f in files))
        print('RELEASE_PACKAGE_COMPLETE',destination,flush=True)
        print(json.dumps({'tag':tag,'files':[{ 'name':f.name,'bytes':f.stat().st_size,'sha256':sha(f)} for f in sorted(destination.iterdir()) if f.is_file()],'checks':report['checks']},indent=2))
        return 0
    except Exception as error:
        (destination/'FAILED.json').write_text(json.dumps({'error':str(error),'readyToUpload':False},indent=2)+'\n')
        raise
if __name__=='__main__':raise SystemExit(main())
