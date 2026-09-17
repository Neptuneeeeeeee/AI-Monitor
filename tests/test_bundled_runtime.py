"""Fixture-only checks for runtime input selection and distribution boundaries."""
from pathlib import Path
import json,sys,unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import bundle_runtime as B

class BundledRuntimeTests(unittest.TestCase):
    def test_runtime_archive_traversal_is_rejected(self):
        for name in ['/python/escape','python/../escape','../python/bin/python3.13']:
            with self.assertRaises(ValueError):B.selected_member(name,'3.13')
    def test_only_real_interpreter_is_selected(self):
        self.assertEqual(B.selected_member('python/bin/python3.13','3.13'),'bin/python3')
        self.assertIsNone(B.selected_member('python/bin/python3','3.13'))
    def test_stdlib_and_shared_library_are_preserved(self):
        self.assertEqual(B.selected_member('python/lib/python3.13/ssl.py','3.13'),'lib/python3.13/ssl.py')
        self.assertEqual(B.selected_member('python/lib/libpython3.13.dylib','3.13'),'lib/libpython3.13.dylib')
    def test_developer_payloads_are_excluded(self):
        for name in ['python/include/Python.h','python/lib/python3.13/site-packages/pip/main.py','python/lib/python3.13/test/test_ssl.py','python/lib/python3.13/__pycache__/ssl.pyc','python/lib/python3.13/tkinter/__init__.py','python/lib/python3.13/lib-dynload/_tkinter.cpython-313-darwin.so']:
            self.assertIsNone(B.selected_member(name,'3.13'),name)
    def test_public_inputs_have_pinned_checksums(self):
        lock=json.loads((ROOT/'Config/runtime-lock.json').read_text())
        self.assertEqual(lock['python']['architecture'],'arm64')
        for item in [lock['python'],lock['certifi'],*lock['upstreamNotices']]:
            self.assertRegex(item['sha256'],r'^[0-9a-f]{64}$')
            self.assertTrue(item['url'].startswith('https://'))
    def test_distributable_never_silently_uses_system_python(self):
        text=(ROOT/'Sources/MonitorShared/AppRuntime.swift').read_text()
        self.assertLess(text.index('appendingPathComponent("Distribution.json")'),text.index('let system = URL'))
        self.assertIn('PYTHONNOUSERSITE',text)
    def test_native_selftest_uses_temporary_home_and_no_accounts(self):
        text=(ROOT/'Sources/MonitorShared/RuntimeSelfCheck.swift').read_text()
        self.assertIn('runtime_smoke.py',text);self.assertIn('env["HOME"] = home.path',text)
        self.assertNotIn('MonitorStore(',text)
    def test_pem_exception_is_narrow_and_public_only(self):
        text=(ROOT/'scripts/verify_bundle.py').read_text()
        self.assertIn("public_ca = f == r/'Python/certificates/cacert.pem'",text)
        self.assertIn("b'PRIVATE KEY' in f.read_bytes()",text)
