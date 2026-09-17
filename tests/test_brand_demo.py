"""Bundled brand provenance and disconnected interaction invariants."""
import hashlib
import json
from pathlib import Path
import re
import struct
import unittest
ROOT=Path(__file__).resolve().parents[1]
class BrandDemoTests(unittest.TestCase):
    def test_new_marks_have_official_source_records(self):
        rows={row['id']:row for row in json.loads((ROOT/'Resources/BrandAssets/sources.json').read_text())}
        domains={'cursor':'cursor.com','minimax':'minimax.io','windsurf':'windsurf.com','kiro':'kiro.dev'}
        for key,domain in domains.items():
            row=rows[key];self.assertIn(domain,row['sourcePage'])
            data=(ROOT/'Resources/BrandAssets'/row['file']).read_bytes()
            self.assertEqual(hashlib.sha256(data).hexdigest(),row['sha256'])
            self.assertEqual(data[:8],b'\x89PNG\r\n\x1a\n')
            w,h=struct.unpack('>II',data[16:24]);self.assertGreaterEqual(min(w,h),32)
    def test_each_new_mark_is_registered(self):
        text=(ROOT/'Sources/MonitorShared/BrandStyle.swift').read_text()
        ids=re.search(r'static let ids = \[(.*?)\]',text).group(1)
        for key in ('cursor','minimax','windsurf','kiro'):self.assertIn('"'+key+'"',ids)
    def test_demo_uses_real_views_and_isolated_defaults(self):
        text=(ROOT/'Sources/MonitorShared/DemoSupport.swift').read_text()
        self.assertIn('MonitorPanel(store: store)',text)
        self.assertIn('servicesEnabled: false',text)
        self.assertIn('".demo." + UUID().uuidString',text)
        self.assertIn('removePersistentDomain(forName: suite)',text)
        self.assertIn('交互预览 · 模拟数据',text)
    def test_demo_does_not_use_real_application_delegate(self):
        text=(ROOT/'Sources/MonitorShared/AppMain.swift').read_text()
        facade=text[text.index('public enum MonitorApplication'):]
        self.assertLess(facade.index('DemoSupport.run('),facade.index('let delegate = AppDelegate()'))
        self.assertIn('DemoSupport.run(args: args); return',facade)
    def test_disconnected_account_actions_fail_closed(self):
        text=(ROOT/'Sources/MonitorShared/APIBalanceStore.swift').read_text()
        for name in ('save','removeKey','grant','openBilling'):
            header=re.search(r'func '+name+r'\([^\n]+\{\n\s*([^\n]+)',text)
            self.assertIsNotNone(header,name);self.assertIn('guard servicesEnabled',header.group(1))
    def test_disconnected_plan_actions_fail_closed(self):
        text=(ROOT/'Sources/MonitorShared/MonitorStore.swift').read_text()
        for name in ('toggleLogin','grantClaude','openWebsite','reconnect','diagnostic','clearQuotaCache','openDataDirectory','refreshCurrent'):
            header=re.search(r'func '+name+r'\([^\n]*\{\n\s*([^\n]+)',text)
            self.assertIsNotNone(header,name);self.assertIn('guard servicesEnabled',header.group(1))
    def test_icons_do_not_recolour_menu_bar(self):
        text=(ROOT/'Sources/MonitorShared/BrandStyle.swift').read_text()
        self.assertIn('image.isTemplate = false',text)
        self.assertIn('renderingMode(.original)',text)
