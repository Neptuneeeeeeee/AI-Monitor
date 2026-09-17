#!/usr/bin/env python3
"""Explicit, edition-scoped install. Default invocation is a read-only plan."""
from __future__ import annotations
import argparse
import datetime as dt
import json
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys
import uuid
from build import PUBLIC, profile_for, output_for

def main() -> int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--project',type=Path,default=PUBLIC)
    p.add_argument('--channel',choices=['public','local'],required=True)
    p.add_argument('--install',action='store_true',help='Actually install this edition; otherwise only print the plan')
    p.add_argument('--replace',action='store_true',help='Allow replacement of the SAME edition, retaining a rollback copy')
    p.add_argument('--launch',action='store_true',help='Launch only after a successful explicit install')
    a=p.parse_args();project=a.project.resolve();profile=profile_for(project,a.channel)
    source=output_for(project,a.channel)/(profile['displayName']+'.app')
    target=Path.home()/'Applications'/(profile['displayName']+'.app')
    if target.name=='Monitor.app' or profile['bundleID']=='local.thalnova.Monitor':raise ValueError('Legacy installation is protected')
    if a.launch and not a.install:raise ValueError('--launch requires --install')
    plan={'channel':a.channel,'source':str(source),'target':str(target),'bundleID':profile['bundleID'],
          'willInstall':a.install,'willLaunch':a.launch,'legacyUntouched':True}
    if not a.install:
        print(json.dumps(plan,indent=2));return 0
    info=plistlib.loads((source/'Contents/Info.plist').read_bytes())
    if info['CFBundleIdentifier']!=profile['bundleID']:raise ValueError('Candidate identity mismatch')
    subprocess.run(['/usr/bin/codesign','--verify','--deep','--strict',str(source)],check=True,timeout=30)
    if target.is_symlink():raise ValueError('Refusing symlinked install target')
    if target.exists():
        installed=plistlib.loads((target/'Contents/Info.plist').read_bytes())
        if installed.get('CFBundleIdentifier')!=profile['bundleID']:raise ValueError('Unrelated application left untouched')
        if not a.replace:raise ValueError('This edition already exists; use --replace after reviewing the candidate')
        processes=subprocess.check_output(['/bin/ps','-axo','pid=,comm='],text=True)
        expected=str(target/'Contents/MacOS'/installed['CFBundleExecutable'])
        if any(line.strip().split(None,1)[-1]==expected for line in processes.splitlines() if line.strip()):
            raise ValueError('Quit this edition before replacement. No running application was terminated.')
    target.parent.mkdir(parents=True,exist_ok=True)
    stage=target.parent/(profile['displayName']+'.installing-'+uuid.uuid4().hex+'.app')
    backup=None
    try:
        subprocess.run(['/usr/bin/ditto','--norsrc','--noextattr',str(source),str(stage)],check=True,timeout=60)
        subprocess.run(['/usr/bin/codesign','--verify','--deep','--strict',str(stage)],check=True,timeout=30)
        if target.exists():
            stamp=dt.datetime.now().strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:8]
            backup=output_for(project,a.channel)/'installed-backups'/stamp/target.name
            backup.parent.mkdir(parents=True);shutil.move(str(target),str(backup))
        try:shutil.move(str(stage),str(target))
        except Exception:
            if backup and backup.exists() and not target.exists():shutil.move(str(backup),str(target))
            raise
        if a.launch:subprocess.run(['/usr/bin/open',str(target)],check=True,timeout=15)
        plan['installed']=True;plan['launchRequested']=a.launch
        print(json.dumps(plan,indent=2));return 0
    finally:
        if stage.exists():shutil.rmtree(stage)

if __name__=='__main__':
    try:raise SystemExit(main())
    except (ValueError,OSError,subprocess.SubprocessError) as error:print('INSTALL_ABORTED:',error,file=sys.stderr);raise SystemExit(1)
