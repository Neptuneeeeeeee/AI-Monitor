from pathlib import Path
import json
import subprocess
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from git_provenance import repository_state

class GitProvenanceTests(unittest.TestCase):
    def repository(self,root):
        subprocess.run(['/usr/bin/git','init','-q',str(root)],check=True)
        (root/'fixture.txt').write_text('synthetic\n')
        subprocess.run(['/usr/bin/git','-C',str(root),'add','fixture.txt'],check=True)
        subprocess.run(['/usr/bin/git','-C',str(root),'-c','user.name=Fixture','-c','user.email=fixture@example.invalid','-c','commit.gpgSign=false','commit','-qm','fixture'],check=True)
    def test_plain_source_export_remains_buildable(self):
        with tempfile.TemporaryDirectory() as d:self.assertFalse(repository_state(Path(d))['available'])
    def test_commit_and_dirty_state(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);self.repository(root);clean=repository_state(root)
            self.assertTrue(clean['available']);self.assertFalse(clean['dirty']);self.assertEqual(len(clean['commit']),40)
            (root/'fixture.txt').write_text('changed\n');dirty=repository_state(root)
            self.assertTrue(dirty['dirty']);self.assertEqual(dirty['commit'],clean['commit'])
    def test_parent_repo_is_not_export_identity(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);self.repository(root);child=root/'export';child.mkdir()
            self.assertFalse(repository_state(child)['available'])
    def test_remote_url_is_not_disclosed(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);self.repository(root)
            subprocess.run(['/usr/bin/git','-C',str(root),'remote','add','origin','https://example.invalid/fixture.git'],check=True)
            self.assertNotIn('example.invalid',json.dumps(repository_state(root)))
    def test_product_name_and_stable_identity(self):
        profile=json.loads((ROOT/'Config/profile.json').read_text())
        self.assertEqual(profile['displayName'],'AI Monitor');self.assertEqual(profile['executableName'],'AIMonitor')
        self.assertEqual(profile['bundleID'],'com.thalnova.aimonitor')
        self.assertEqual(profile['dataDirectoryName'],'AI Monitor')
