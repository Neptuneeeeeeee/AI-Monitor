#!/usr/bin/env python3
"""Run fixture-only tests with network disabled and disposable account storage."""
from pathlib import Path
import os
import socket
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
def main():
    with tempfile.TemporaryDirectory(prefix='monitor-tests-') as folder:
        env={'HOME':folder,'MONITOR_TEST_MODE':'1','MONITOR_DATA_DIR':str(Path(folder)/'data'),'PYTHONDONTWRITEBYTECODE':'1'}
        # Do not inherit API credentials or upstream CLI configuration from a shell.
        safe={k:v for k,v in os.environ.items() if k in {'PATH','TMPDIR','LANG','LC_ALL'}}
        safe.update(env)
        def denied(*args,**kwargs):raise AssertionError('Network is disabled in unit tests')
        with patch.dict(os.environ,safe,clear=True),patch.object(socket.socket,'connect',denied),patch.object(socket,'create_connection',denied):
            sys.path.insert(0,str(ROOT/'collector'))
            suite=unittest.defaultTestLoader.discover(str(ROOT/'tests'),pattern='test_*.py')
            result=unittest.TextTestRunner(verbosity=2).run(suite)
        return 0 if result.wasSuccessful() else 1
if __name__=='__main__':raise SystemExit(main())
