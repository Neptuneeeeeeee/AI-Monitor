#!/usr/bin/env python3
"""Conservative source-boundary checks, not a complete security/license audit."""
from pathlib import Path
import json
import re
import sys

ALLOWED={'Sources','Support','collector','Resources','Config','scripts','tests','docs','.github',
         'Package.swift','Package.resolved','README.md','README.zh-CN.md','LICENSE','LICENSE_PENDING.md',
         'THIRD_PARTY_NOTICES.md','PRIVACY.md','SECURITY.md','CONTRIBUTING.md','CHANGELOG.md','.gitignore','.gitattributes'}
GENERATED={'.git','.build','.swiftpm','dist','logs','__pycache__','.DS_Store'}
SECRET_PATTERNS=[r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
                 r'(?<![A-Za-z0-9])(?:sk-(?:proj-|ant-api\d+-)?[A-Za-z0-9_-]{24,}|gh[pousr]_[A-Za-z0-9]{24,}|github_pat_[A-Za-z0-9_]{30,})']

def audit_source(root:Path)->dict:
    problems=[];scanned=0
    for f in root.iterdir():
        if f.name not in ALLOWED|GENERATED:problems.append(str(f.relative_to(root))+': not in public allowlist')
    for name in ALLOWED:
        base=root/name
        if not base.exists():continue
        for f in ([base] if base.is_file() else base.rglob('*')):
            if '__pycache__' in f.parts:continue
            if f.is_symlink():problems.append(str(f.relative_to(root))+': symlink rejected');continue
            if not f.is_file() or f.suffix not in ('.py','.swift','.sh','.md','.json','.yml','.yaml','.txt'):continue
            text=f.read_text();scanned+=1
            for i,line in enumerate(text.splitlines(),1):
                if any(re.search(pattern,line) for pattern in SECRET_PATTERNS):problems.append(f'{f.relative_to(root)}:{i}: possible secret (value omitted)')
            if 'Sources' in f.relative_to(root).parts and re.search(r'^\s*import\s+LocalExperiments\b',text,re.M):
                problems.append(str(f.relative_to(root))+': public target imports a private module')
    manifest=(root/'Package.swift').read_text()
    if re.search(r'\.package\([^\n]*path\s*:',manifest):problems.append('Public package cannot require adjacent local packages')
    profile=json.loads((root/'Config/profile.json').read_text())
    if profile.get('channel')!='public' or profile.get('experimentalModules'):problems.append('Not a public profile')
    if problems:raise ValueError('\n'.join(problems))
    result={'passed':True,'scannedTextFiles':scanned,'secretScan':'limited-patterns','licenseReview':'pending'}
    print('PUBLIC_SOURCE_AUDIT',json.dumps(result),flush=True);return result

if __name__=='__main__':
    try:audit_source(Path(__file__).resolve().parents[1])
    except (ValueError,OSError) as error:print('AUDIT_FAILED',error,file=sys.stderr);raise SystemExit(1)
