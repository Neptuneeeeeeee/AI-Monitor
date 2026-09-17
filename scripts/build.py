#!/usr/bin/env python3
"""Build an isolated candidate; never installs, launches, or reads live helpers."""
from __future__ import annotations
import argparse
import datetime as dt
import fcntl
import hashlib
import json
import os
from pathlib import Path
import platform
import plistlib
import shutil
import subprocess
import sys
import tempfile
import uuid
from git_provenance import repository_state

PUBLIC = Path(__file__).resolve().parents[1]
PROVIDERS = {'claude','kimi','codex','glm','copilot','antigravity'}

def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def profile_for(project: Path, expected: str) -> dict:
    doc = json.loads((project/'Config/profile.json').read_text())
    name = 'AI Monitor' + (' Local' if expected == 'local' else '')
    identifier = 'com.thalnova.aimonitor' + ('.local' if expected == 'local' else '')
    executable = 'AIMonitor' + ('Local' if expected == 'local' else '')
    if (expected not in ('public','local') or doc.get('schema') != 1
            or doc.get('channel') != expected or doc.get('bundleID') != identifier
            or doc.get('displayName') != name or doc.get('dataDirectoryName') != name
            or doc.get('executableName') != executable
            or not set(doc.get('defaultEnabledProviders',[])) <= PROVIDERS
            or (expected == 'public' and (doc.get('experimentalModules') or doc.get('badge')))):
        raise ValueError('Invalid profile or cross-edition build requested')
    entitlements = plistlib.loads((project/'Config/Entitlements.plist').read_bytes())
    if not isinstance(entitlements,dict): raise ValueError('Invalid entitlements')
    if expected == 'public' and entitlements:
        raise ValueError('Public entitlements must be reviewed before expanding permissions')
    return doc

def output_for(project: Path, channel: str) -> Path:
    workspace = project.parent
    return workspace/'output'/channel if (workspace/'WORKSPACE.json').is_file() else project/'dist'

def source_hashes(root: Path) -> dict:
    result = {}
    for name in ['Sources','Support','collector','Resources','Config','scripts','tests']:
        base = root/name
        if not base.exists(): continue
        for f in sorted(base.rglob('*')):
            if f.is_file() and not f.is_symlink() and '__pycache__' not in f.parts and f.name != '.DS_Store':
                result[str(f.relative_to(root))] = digest(f)
    result['Package.swift'] = digest(root/'Package.swift')
    return result

def run(command: list[str], cwd: Path, env: dict, timeout: int = 900, capture: bool = False) -> str:
    print('+', ' '.join(map(str,command)),flush=True)
    result = subprocess.run(list(map(str,command)),cwd=cwd,env=env,check=True,
                            timeout=timeout,text=True,stdout=subprocess.PIPE if capture else None)
    return result.stdout.strip() if capture else ''

def clean_copy(source: Path, target: Path) -> str:
    # Copy bytes and executable mode, not Finder/resource-fork metadata.
    shutil.copyfile(source,target)
    shutil.copymode(source,target)
    return str(target)

def sign(app: Path, cwd: Path, env: dict, entitlements: Path | None = None) -> None:
    # Only generated bundle files. Never remove quarantine or alter system policy.
    if any(path.is_symlink() for path in [app,*app.rglob('*')]):
        raise ValueError('Symlink in generated bundle')
    for name in ('com.apple.FinderInfo','com.apple.ResourceFork'):
        # Apple's Python does not expose Linux's os.listxattr API. Missing
        # attributes are harmless; codesign below remains the decisive check.
        subprocess.run(['/usr/bin/xattr','-dr',name,str(app)],cwd=cwd,env=env,
                       stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=30)
    args = ['/usr/bin/codesign','--force','--sign','-']
    if entitlements is not None: args += ['--entitlements',str(entitlements)]
    run(args+[str(app)],cwd,env)
    run(['/usr/bin/codesign','--verify','--deep','--strict',str(app)],cwd,env)

def helper(template: str, executable: str, suffix: str, label: str,
           profile: dict, cache: Path, env: dict, arch: str) -> tuple[Path,dict]:
    identifier = profile['bundleID']+suffix
    source = (PUBLIC/'Support'/template).read_text().replace('__KEYCHAIN_PREFIX__',profile['bundleID']+'.').replace('__HELPER_ID__',identifier)
    if '__KEYCHAIN_PREFIX__' in source or '__HELPER_ID__' in source: raise ValueError('Unresolved helper identity')
    compiler = run(['/usr/bin/swiftc','--version'],PUBLIC,env,30,True)
    signature = hashlib.sha256((source+'\n'+compiler+'\n'+arch).encode()).hexdigest()
    folder = cache/'Helpers'/signature
    app = folder/(profile['displayName']+' '+label+'.app')
    binary = app/'Contents/MacOS'/executable
    manifest = folder/'identity.json'
    if binary.is_file() and manifest.is_file():
        metadata = json.loads(manifest.read_text())
        if metadata.get('bundleID') == identifier and metadata.get('binarySHA256') == digest(binary):
            run(['/usr/bin/codesign','--verify','--strict',str(app)],PUBLIC,env)
            return app,metadata
        raise RuntimeError('Own helper cache failed validation; inspect before retrying')
    folder.mkdir(parents=True,exist_ok=True)
    source_path = folder/'main.swift';source_path.write_text(source)
    binary.parent.mkdir(parents=True,exist_ok=True)
    run(['/usr/bin/swiftc','-O','-target',arch+'-apple-macosx14.0',
         '-module-cache-path',str(cache/'ModuleCache'),str(source_path),'-o',str(binary)],PUBLIC,env)
    info = {'CFBundleExecutable':executable,'CFBundleIdentifier':identifier,
            'CFBundleName':profile['displayName']+' '+label,'CFBundleDisplayName':profile['displayName']+' '+label,
            'CFBundlePackageType':'APPL','CFBundleVersion':'1','CFBundleShortVersionString':'1.0',
            'LSUIElement':True,'LSMinimumSystemVersion':'14.0'}
    (app/'Contents/Info.plist').write_bytes(plistlib.dumps(info))
    sign(app,PUBLIC,env)
    metadata = {'version':1,'channel':profile['channel'],'bundleID':identifier,'sourceSHA256':signature,'binarySHA256':digest(binary)}
    manifest.write_text(json.dumps(metadata,indent=2)+'\n')
    return app,metadata

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project',type=Path,default=PUBLIC)
    parser.add_argument('--expected-channel',choices=['public','local'],default='public')
    parser.add_argument('--jobs',type=int,default=2)
    parser.add_argument('--skip-tests',action='store_true',help='Developer candidate only; recorded in build receipt')
    args = parser.parse_args()
    project = args.project.resolve(); channel = args.expected_channel
    if channel == 'public' and project != PUBLIC: raise ValueError('Public entry must build its own checkout')
    if channel == 'local' and project == PUBLIC: raise ValueError('Local entry needs an independent project')
    if not 1 <= args.jobs <= 16: raise ValueError('jobs must be 1..16')
    profile = profile_for(project,channel)
    # Audit only the public source boundary, never inspect private adjacent folders.
    from audit_public import audit_source
    audit_source(PUBLIC)
    public_before = source_hashes(PUBLIC)
    public_git_before = repository_state(PUBLIC)
    local_git_before = repository_state(project) if channel == "local" else None
    local_before = source_hashes(project) if channel == 'local' else {}
    output = output_for(project,channel);output.mkdir(parents=True,exist_ok=True)
    cache = Path.home()/'Library/Caches/AIMonitor'/channel.capitalize()
    cache.mkdir(parents=True,exist_ok=True)
    lock = (cache/'build.lock').open('a')
    try: fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError: raise RuntimeError('Another build of this edition is already running')
    env = {k:v for k,v in os.environ.items() if k in {'HOME','USER','LOGNAME','TMPDIR','LANG','LC_ALL','DEVELOPER_DIR','SDKROOT'}}
    env.update(PATH='/usr/bin:/bin:/usr/sbin:/sbin',PYTHONDONTWRITEBYTECODE='1')
    arch = platform.machine()
    if arch not in ('arm64','x86_64'): raise RuntimeError('Build on a supported Mac')
    jobs = str(args.jobs)
    if not args.skip_tests:
        run([sys.executable,str(PUBLIC/'scripts/test_python.py')],PUBLIC,env,180)
        if channel == 'local' and (project/'tests').is_dir():
            run([sys.executable,'-m','unittest','discover','-s','tests','-v'],project,env,180)
        run(['/usr/bin/swift','run','--package-path',str(PUBLIC),'--scratch-path',str(cache/'CoreChecks'),'-j',jobs,'MonitorCoreChecks'],PUBLIC,env,900)
    run(['/usr/bin/swift','build','--package-path',str(project),'--scratch-path',str(cache/'SwiftPM'),'-c','release','--product',profile['executableName'],'-j',jobs],project,env,1200)
    bin_path = Path(run(['/usr/bin/swift','build','--package-path',str(project),'--scratch-path',str(cache/'SwiftPM'),'-c','release','--show-bin-path'],project,env,120,True))
    stamp = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    stage = cache/'Packaging'/uuid.uuid4().hex;stage.mkdir(parents=True,mode=0o700)
    app = stage/(profile['displayName']+'.app')
    resources=app/'Contents/Resources';(app/'Contents/MacOS').mkdir(parents=True);resources.mkdir()
    try:
        clean_copy(bin_path/profile['executableName'],app/'Contents/MacOS'/profile['executableName'])
        collector=resources/'collector';collector.mkdir()
        for f in sorted((PUBLIC/'collector').glob('*.py')):
            if f.is_symlink(): raise ValueError('Symlinked collector rejected')
            clean_copy(f,collector/f.name)
        data=json.dumps(profile,indent=2)+'\n'
        (collector/'runtime.json').write_text(data);(resources/'RuntimeProfile.json').write_text(data)
        assets=resources/'BrandAssets';assets.mkdir()
        for f in sorted((PUBLIC/'Resources/BrandAssets').glob('*.png')):
            if f.is_symlink():raise ValueError('Symlinked asset rejected')
            clean_copy(f,assets/f.name)
        clean_copy(PUBLIC/'Resources/AppIcon.icns',resources/'AppIcon.icns')
        for template,exe,suffix,label,destination in [
            ('KeychainBridge.swift','MonitorKeychain','.Keychain.v1','Keychain','AuthBridge'),
            ('APIVault.swift','MonitorAPIVault','.APIVault.v1','API Vault','APIVault')]:
            bundle,metadata=helper(template,exe,suffix,label,profile,cache,env,arch)
            target=resources/destination;target.mkdir()
            shutil.copytree(bundle,target/bundle.name,copy_function=clean_copy)
            (target/'identity.json').write_text(json.dumps(metadata,indent=2)+'\n')
        info={'CFBundleDevelopmentRegion':'en','CFBundleExecutable':profile['executableName'],
              'CFBundleIconFile':'AppIcon','CFBundleIdentifier':profile['bundleID'],
              'CFBundleInfoDictionaryVersion':'6.0','CFBundleName':profile['displayName'],
              'CFBundleDisplayName':profile['displayName'],'CFBundlePackageType':'APPL',
              'CFBundleShortVersionString':profile['version'],'CFBundleVersion':profile['buildNumber'],
              'LSMinimumSystemVersion':'14.0','LSUIElement':True,'NSHighResolutionCapable':True,'NSPrincipalClass':'NSApplication'}
        (app/'Contents/Info.plist').write_bytes(plistlib.dumps(info))
        sign(app,project,env,project/'Config/Entitlements.plist')
        run([sys.executable,str(PUBLIC/'scripts/verify_bundle.py'),str(app),'--channel',channel],PUBLIC,env,180)
        if source_hashes(PUBLIC) != public_before or (channel == 'local' and source_hashes(project) != local_before):
            raise RuntimeError('Sources changed while building; rebuild before using this candidate')
        if repository_state(PUBLIC) != public_git_before or (channel == 'local' and repository_state(project) != local_git_before):
            raise RuntimeError('Git revision/worktree changed while building; rebuild this candidate')
        # Desktop/file-provider folders can reattach Finder metadata to .app
        # directories. Keep each signed candidate immutable in an edition cache;
        # output contains only a local shortcut plus the real portable ZIP.
        candidate_root=cache/'Candidates'/(stamp+'-'+uuid.uuid4().hex[:10])
        candidate_root.mkdir(parents=True,mode=0o700)
        final=candidate_root/app.name
        shutil.move(str(app),str(final))
        run(['/usr/bin/codesign','--verify','--deep','--strict',str(final)],project,env)
        visible=output/final.name
        if visible.exists() or visible.is_symlink():
            previous=plistlib.loads((visible/'Contents/Info.plist').read_bytes()) if visible.exists() else {}
            if visible.exists() and previous.get('CFBundleIdentifier') != profile['bundleID']:
                raise ValueError('Refusing to replace an unrelated candidate shortcut')
            archive=output/'previous'/(stamp+'-'+uuid.uuid4().hex[:8]);archive.mkdir(parents=True)
            shutil.move(str(visible),str(archive/visible.name))
        shortcut=output/('.shortcut-'+uuid.uuid4().hex)
        shortcut.symlink_to(final,target_is_directory=True)
        os.replace(shortcut,visible)
        package=output/(profile['executableName']+'-'+profile['version']+'-'+arch+'-candidate.zip')
        temporary_zip=output/('.zip-'+uuid.uuid4().hex+'.zip')
        run(['/usr/bin/ditto','-c','-k','--norsrc','--noextattr','--keepParent',str(final),str(temporary_zip)],project,env)
        os.replace(temporary_zip,package)
        hashes=source_hashes(PUBLIC)
        report={'schema':1,'channel':channel,'bundleID':profile['bundleID'],'version':profile['version'],'buildNumber':profile['buildNumber'],'builtAtUTC':stamp,
                'architecture':arch,'app':visible.name,'appLocation':str(final),'appIsLocalShortcut':True,'archive':package.name,'archiveSHA256':digest(package),
                'testsRun':not args.skip_tests,'signed':'ad-hoc','distributionReady':False,
                'limitations':['Python runtime is not bundled','Developer ID signing and notarization not performed','Open-source license and third-party redistribution review pending'],
                'publicSourceHashes':hashes,'localSourceHashes':local_before,
                'publicGit':public_git_before,'localGit':local_git_before,
                'appFileHashes':{str(f.relative_to(final)):digest(f) for f in sorted(final.rglob('*')) if f.is_file()}}
        (output/'BUILD.json').write_text(json.dumps(report,indent=2)+'\n')
        (output/'SHA256SUMS').write_text(report['archiveSHA256']+'  '+package.name+'\n')
        (output/'CANDIDATE_README.txt').write_text('The .app entry is a local shortcut to a signed candidate in this edition\'s cache.\nShare the actual ZIP, never the shortcut. Cache cleanup can invalidate the shortcut; rebuilding recreates it.\nDeveloper candidate only: see BUILD.json for distribution limitations.\n')
        print('BUILD_COMPLETE',final,flush=True);print('CANDIDATE_ONLY_NOT_INSTALLED',package,flush=True)
        return 0
    finally:
        if stage.exists():shutil.rmtree(stage)
        fcntl.flock(lock,fcntl.LOCK_UN);lock.close()

if __name__=='__main__':
    try:raise SystemExit(main())
    except (ValueError,RuntimeError,OSError,subprocess.SubprocessError) as error:
        print('BUILD_FAILED:',error,file=sys.stderr);raise SystemExit(1)
