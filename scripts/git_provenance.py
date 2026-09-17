#!/usr/bin/env python3
"""Read-only, local Git provenance. Never fetches, pushes, or exposes remotes."""
from pathlib import Path
import subprocess

def repository_state(root: Path) -> dict:
    root = root.resolve()
    def read(*args):
        result = subprocess.run(['/usr/bin/git','-C',str(root),*args],capture_output=True,text=True,timeout=15)
        return result.returncode, result.stdout.strip()
    try:
        code,top = read('rev-parse','--show-toplevel')
        if code or Path(top).resolve()!=root:
            return {'available':False,'reason':'Source export without its own Git repository'}
        code,commit = read('rev-parse','--verify','HEAD')
        if code:
            return {'available':False,'reason':'No committed revision'}
        _,branch = read('symbolic-ref','--quiet','--short','HEAD')
        code,status = read('status','--porcelain=v1','--untracked-files=normal')
        if code:raise RuntimeError('Cannot read source worktree state')
        return {'available':True,'commit':commit,'branch':branch or None,'dirty':bool(status)}
    except OSError:
        return {'available':False,'reason':'Git executable unavailable'}
