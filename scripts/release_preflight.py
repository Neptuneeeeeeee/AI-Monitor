#!/usr/bin/env python3
"""Read-only formal-release gate. A developer candidate is not a public release."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from audit_public import audit_source
from build import PUBLIC, output_for, source_hashes

def inspect() -> dict:
    blockers=[]
    try:audit_source(PUBLIC)
    except (ValueError,OSError) as error:blockers.append('Source audit: '+str(error))
    if not (PUBLIC/'LICENSE').is_file() or (PUBLIC/'LICENSE_PENDING.md').exists():
        blockers.append('Owner has not selected and approved the source license')
    approval_path=PUBLIC/'Config/release-review.json'
    approval=json.loads(approval_path.read_text()) if approval_path.exists() else {}
    if approval.get('thirdPartyReviewComplete') is not True:blockers.append('Third-party code and asset redistribution review pending')
    if approval.get('cleanMacTested') is not True:blockers.append('Clean-Mac installation test pending')
    out=output_for(PUBLIC,'public');receipt=out/'BUILD.json'
    if not receipt.exists():blockers.append('No completed public build receipt');return {'ready':False,'blockers':blockers}
    report=json.loads(receipt.read_text());app=out/report['app']
    if report.get('channel')!='public':blockers.append('Wrong candidate channel')
    if report.get('testsRun') is not True:blockers.append('Candidate did not run the required tests')
    if report.get('publicSourceHashes')!=source_hashes(PUBLIC):blockers.append('Sources changed after this candidate was built')
    actual={str(f.relative_to(app)):hashlib.sha256(f.read_bytes()).hexdigest() for f in app.rglob('*') if f.is_file()}
    if report.get('appFileHashes')!=actual:blockers.append('Application differs from its verified build receipt')
    archive=out/report['archive']
    if not archive.is_file() or hashlib.sha256(archive.read_bytes()).hexdigest()!=report['archiveSHA256']:blockers.append('Archive is missing or its checksum differs')
    if not (app/'Contents/Resources/Python/bin/python3').is_file():blockers.append('Supported Python runtime is not bundled')
    signature=subprocess.run(['/usr/bin/codesign','-dv','--verbose=4',str(app)],capture_output=True,text=True)
    if signature.returncode or 'Authority=Developer ID Application:' not in signature.stderr:
        blockers.append('No Developer ID Application signature')
    else:
        if subprocess.run(['/usr/bin/codesign','--verify','--deep','--strict',str(app)],capture_output=True).returncode:blockers.append('Code-signature integrity check failed')
        if subprocess.run(['/usr/bin/xcrun','stapler','validate',str(app)],capture_output=True,timeout=90).returncode:blockers.append('Notarization ticket validation failed')
    git=subprocess.run(['git','status','--porcelain'],cwd=PUBLIC,capture_output=True,text=True)
    commit=subprocess.run(['git','rev-parse','HEAD'],cwd=PUBLIC,capture_output=True,text=True)
    if git.returncode or git.stdout.strip() or commit.returncode:blockers.append('A clean committed public checkout is required')
    elif approval.get('approvedSourceCommit')!=commit.stdout.strip():blockers.append('The current source commit is not approved for release')
    return {'ready':not blockers,'candidate':report.get('archive'),'blockers':blockers,'publishingPerformed':False}

if __name__=='__main__':
    try:
        result=inspect();print(json.dumps(result,indent=2));raise SystemExit(0 if result['ready'] else 2)
    except (OSError,ValueError,subprocess.SubprocessError) as error:
        print(json.dumps({'ready':False,'error':str(error),'publishingPerformed':False},indent=2));raise SystemExit(2)
