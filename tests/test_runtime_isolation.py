import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'collector'));sys.path.insert(0,str(ROOT/'scripts'))
from runtime_config import PROFILE,KEYCHAIN_PREFIX
from credentials import own_key
from build import profile_for

class RuntimeIsolationTests(unittest.TestCase):
    def test_public_namespace(self):self.assertEqual(KEYCHAIN_PREFIX,'com.thalnova.aimonitor.')
    def test_no_default_account_scan(self):self.assertEqual(PROFILE['defaultEnabledProviders'],[])
    def test_no_private_modules(self):self.assertEqual(PROFILE['experimentalModules'],[])
    def test_own_key_uses_new_namespace(self):
        with patch('credentials.keychain',return_value='fixture') as f:
            self.assertEqual(own_key('kimi'),'fixture');f.assert_called_once_with('com.thalnova.aimonitor.kimi')
    def test_cross_profile_rejected(self):
        with self.assertRaises(ValueError):profile_for(ROOT,'local')
    def test_production_override_rejected(self):
        env={**os.environ,'MONITOR_DATA_DIR':'/tmp/monitor-test','PYTHONPATH':str(ROOT/'collector')};env.pop('MONITOR_TEST_MODE',None)
        r=subprocess.run([sys.executable,'-c','import runtime_config'],env=env,capture_output=True,text=True)
        self.assertNotEqual(r.returncode,0)
    def test_test_override_cannot_target_legacy(self):
        env={**os.environ,'MONITOR_TEST_MODE':'1','MONITOR_DATA_DIR':str(Path.home()/'Library/Application Support/Monitor'),'PYTHONPATH':str(ROOT/'collector')}
        r=subprocess.run([sys.executable,'-c','import runtime_config'],env=env,capture_output=True,text=True)
        self.assertNotEqual(r.returncode,0)
    def test_public_package_has_no_local_dependency(self):
        self.assertNotIn('.package(', (ROOT/'Package.swift').read_text())
    def test_swift_test_path_case(self):self.assertIn('path: "tests/MonitorCoreTests"',(ROOT/'Package.swift').read_text())
    def test_no_legacy_live_paths(self):
        for folder in ['Sources','collector']:
            for f in (ROOT/folder).rglob('*'):
                if f.suffix in ('.swift','.py'):
                    self.assertNotIn('local.thalnova.Monitor',f.read_text(),str(f))
    def test_helper_templates_have_placeholders(self):
        for name in ['APIVault.swift','KeychainBridge.swift']:
            text=(ROOT/'Support'/name).read_text();self.assertIn('__KEYCHAIN_PREFIX__',text);self.assertNotIn('local.thalnova.Monitor',text)
    def test_invalid_entitlements_rejected(self):
        import plistlib
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);(p/'Config').mkdir();(p/'Config/profile.json').write_text((ROOT/'Config/profile.json').read_text())
            (p/'Config/Entitlements.plist').write_bytes(plistlib.dumps({'com.apple.security.automation.apple-events':True}))
            with self.assertRaises(ValueError):profile_for(p,'public')
