#!/usr/bin/env python3
"""Build a relocatable runtime from SHA-256-pinned public upstream artifacts."""
from __future__ import annotations
import hashlib,json,os,platform,shutil,subprocess,tarfile,urllib.parse,urllib.request,zipfile
from pathlib import Path,PurePosixPath
PUBLIC=Path(__file__).resolve().parents[1]
MACH_MAGICS={b'\xcf\xfa\xed\xfe',b'\xfe\xed\xfa\xcf',b'\xca\xfe\xba\xbe',b'\xbe\xba\xfe\xca'}
def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for data in iter(lambda:f.read(1024*1024),b''):h.update(data)
    return h.hexdigest()
def obtain(item,cache):
    parts=urllib.parse.urlsplit(item['url'])
    if parts.scheme!='https' or parts.hostname not in {'github.com','raw.githubusercontent.com','files.pythonhosted.org'}:raise ValueError('Unapproved runtime upstream')
    name=item['filename']
    if Path(name).name!=name:raise ValueError('Invalid input filename')
    cache.mkdir(parents=True,exist_ok=True);out=cache/name
    if out.is_file() and sha(out)==item['sha256']:return out
    temp=cache/(name+'.partial')
    try:
        with urllib.request.urlopen(item['url'],timeout=60) as response,temp.open('wb') as f:
            size=0
            while True:
                data=response.read(1024*1024)
                if not data:break
                size+=len(data)
                if size>150*1024*1024:raise ValueError('Download too large')
                f.write(data)
        if sha(temp)!=item['sha256']:raise ValueError('Upstream checksum mismatch')
        os.replace(temp,out)
    finally:
        if temp.exists():temp.unlink()
    return out

def selected_member(name,minor):
    p=PurePosixPath(name)
    if p.is_absolute() or '..' in p.parts:raise ValueError('Unsafe archive path')
    if name==f'python/bin/python{minor}':return 'bin/python3'
    if name==f'python/lib/libpython{minor}.dylib':return f'lib/libpython{minor}.dylib'
    prefix=f'python/lib/python{minor}/'
    if not name.startswith(prefix):return None
    parts=PurePosixPath(name[len(prefix):]).parts
    if not parts:return None
    if any(x in {'site-packages','__pycache__','test','tests','ensurepip','idlelib','tkinter','turtledemo'} for x in parts):return None
    if parts[0].startswith('config-') or '_tkinter.' in name or name.endswith(('.pyc','.pyo','.a')):return None
    return name[len('python/'):]

def prepare(destination,env):
    lock=json.loads((PUBLIC/'Config/runtime-lock.json').read_text())
    if platform.machine()!=lock['python']['architecture']:raise ValueError('No pinned runtime for this architecture')
    if destination.exists():raise ValueError('Runtime destination must be new')
    cache=Path.home()/'Library/Caches/AIMonitor/DistributionInputs'
    archive=obtain(lock['python'],cache);minor='.'.join(lock['python']['version'].split('.')[:2])
    destination.mkdir(parents=True);count=0;size=0
    with tarfile.open(archive,'r:gz') as tar:
        for member in tar:
            relative=selected_member(member.name,minor)
            if relative is None or member.isdir():continue
            if not member.isfile():raise ValueError('Selected member must be a regular file')
            size+=member.size;count+=1
            if count>6000 or size>250*1024*1024:raise ValueError('Unexpected archive expansion')
            target=destination/relative;target.parent.mkdir(parents=True,exist_ok=True)
            source=tar.extractfile(member)
            if source is None:raise ValueError('Unreadable member')
            with source,target.open('wb') as out:shutil.copyfileobj(source,out)
            target.chmod(0o755 if member.mode&0o111 else 0o644)
    if not (destination/'bin/python3').is_file():raise ValueError('Missing Python executable')
    notices=destination/'licenses';notices.mkdir()
    for item in lock['upstreamNotices']:shutil.copyfile(obtain(item,cache/'licenses'),notices/item['filename'])
    cert=obtain(lock['certifi'],cache);certificates=destination/'certificates';certificates.mkdir()
    with zipfile.ZipFile(cert) as wheel:
        ca=wheel.read('certifi/cacert.pem')
        if b'PRIVATE KEY' in ca or ca.count(b'BEGIN CERTIFICATE')<50:raise ValueError('Not a public trust-root bundle')
        (certificates/'cacert.pem').write_bytes(ca)
        name=next(n for n in wheel.namelist() if n.endswith('/licenses/LICENSE'))
        (notices/'CERTIFI-LICENSE.txt').write_bytes(wheel.read(name))
    (destination/f'lib/python{minor}/sitecustomize.py').write_text('import os\nfrom pathlib import Path\nos.environ.setdefault("SSL_CERT_FILE",str(Path(__file__).resolve().parents[2]/"certificates/cacert.pem"))\n')
    (destination/'RUNTIME-NOTICE.txt').write_text('CPython runtime from astral-sh/python-build-standalone.\nUnused headers, pip, Tk and tests are omitted. No user packages or accounts are included.\nOriginal notices are preserved in licenses/ and the standard-library LICENSE.txt.\ncertificates/cacert.pem is the public Mozilla root set from certifi (MPL-2.0).\nPinned artifact hashes are recorded in provenance.json.\n')
    binaries=[]
    for file in sorted(destination.rglob('*')):
        if not file.is_file():continue
        with file.open('rb') as f:magic=f.read(4)
        if magic not in MACH_MAGICS:continue
        subprocess.run(['/usr/bin/codesign','--force','--sign','-',str(file)],check=True,env=env,timeout=40)
        subprocess.run(['/usr/bin/codesign','--verify','--strict',str(file)],check=True,env=env,timeout=40)
        linked=subprocess.check_output(['/usr/bin/otool','-L',str(file)],text=True,timeout=30)
        for line in linked.splitlines()[1:]:
            dependency=line.strip().split(' (',1)[0]
            if dependency.startswith('/') and not dependency.startswith(('/usr/lib/','/System/Library/')):raise ValueError('External runtime dependency: '+dependency)
        binaries.append(str(file.relative_to(destination)))
    report={**lock,'publicCACertificateSHA256':sha(certificates/'cacert.pem'),'includedFileCount':count,'signedMachOFiles':binaries,'compiledFromLocalPython':False}
    (destination/'provenance.json').write_text(json.dumps(report,indent=2)+'\n')
    print('BUNDLED_PYTHON_READY',lock['python']['version'],count,'files',flush=True)
    return report
