"""Regressions discovered during user-authorized real-client validation."""
from pathlib import Path
import hashlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'collector'))
import local_plan_store as store
import monitor
from core import MonitorError

class LiveCompatibilityTests(unittest.TestCase):
    def test_clone_supports_database_above_fallback_copy_limit(self):
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/'original';target=Path(directory)/'copy'
            source.write_bytes(b'synthetic non-credential database bytes')
            def clone(command,**kwargs):
                self.assertEqual(command[:2],['/bin/cp','-c'])
                shutil.copyfile(command[2],command[3])
                return subprocess.CompletedProcess(command,0)
            with patch.object(store.sys,'platform','darwin'),patch.object(store,'MAX_FALLBACK_COPY_BYTES',1),patch.object(store.subprocess,'run',side_effect=clone):
                store.snapshot_copy(source,target)
            self.assertEqual(target.read_bytes(),source.read_bytes())
            self.assertEqual(target.stat().st_mode & 0o777,0o600)
    def test_no_large_fallback_when_clone_is_unavailable(self):
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/'original';target=Path(directory)/'copy'
            source.write_bytes(b'synthetic')
            with patch.object(store.sys,'platform','darwin'),patch.object(store,'MAX_FALLBACK_COPY_BYTES',1),patch.object(store.subprocess,'run',return_value=subprocess.CompletedProcess([],1)):
                with self.assertRaises(MonitorError):store.snapshot_copy(source,target)
            self.assertFalse(target.exists())
    def test_no_symlinked_database_clone(self):
        with tempfile.TemporaryDirectory() as directory:
            original=Path(directory)/'original';original.write_bytes(b'synthetic')
            link=Path(directory)/'link';link.symlink_to(original)
            with self.assertRaises(MonitorError):store.snapshot_copy(link,Path(directory)/'copy')
    def test_cursor_unrelated_database_write_does_not_change_account_context(self):
        with patch.object(store,'read_app_value',side_effect=[('synthetic-session',10),('synthetic-session',20)]):
            first=monitor.generation('cursor','cn');second=monitor.generation('cursor','cn')
        self.assertEqual(first,second)
        self.assertNotIn('synthetic-session',first)
    def test_cursor_different_session_invalidates_cached_account(self):
        with patch.object(store,'read_app_value',side_effect=[('synthetic-one',10),('synthetic-two',10)]):
            self.assertNotEqual(monitor.generation('cursor','cn'),monitor.generation('cursor','cn'))
    def test_cursor_no_session_no_identity(self):
        with patch.object(store,'read_app_value',return_value=(None,10)):
            self.assertIsNone(monitor.generation('cursor','cn'))
