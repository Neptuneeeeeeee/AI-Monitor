import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
class InstallSafetyTests(unittest.TestCase):
    def invoke(self,home,*args):
        return subprocess.run([sys.executable,str(ROOT/'scripts/install.py'),'--channel','public',*args],env={**os.environ,'HOME':home},capture_output=True,text=True)
    def test_default_is_read_only_plan(self):
        with tempfile.TemporaryDirectory() as home:
            result=self.invoke(home);self.assertEqual(result.returncode,0,result.stderr)
            doc=json.loads(result.stdout);self.assertFalse(doc['willInstall']);self.assertFalse(doc['willLaunch']);self.assertFalse((Path(home)/'Applications').exists())
    def test_target_never_legacy(self):
        with tempfile.TemporaryDirectory() as home:
            doc=json.loads(self.invoke(home).stdout);self.assertEqual(Path(doc['target']).name,'AI Monitor.app');self.assertEqual(doc['bundleID'],'com.thalnova.aimonitor')
    def test_launch_requires_explicit_install(self):
        with tempfile.TemporaryDirectory() as home:
            r=self.invoke(home,'--launch');self.assertNotEqual(r.returncode,0);self.assertFalse((Path(home)/'Applications').exists())
    def test_cross_channel_refused_before_write(self):
        with tempfile.TemporaryDirectory() as home:
            r=self.invoke(home,'--channel','local','--install');self.assertNotEqual(r.returncode,0);self.assertFalse((Path(home)/'Applications').exists())
    def test_install_does_not_kill_apps(self):
        source=(ROOT/'scripts/install.py').read_text();self.assertNotIn('os.kill',source);self.assertNotIn('pkill',source)
