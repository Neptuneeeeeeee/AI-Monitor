"""Display-language catalog: completeness, placeholders, protected terms and coverage."""
import json
from pathlib import Path
import re
import unittest
ROOT = Path(__file__).resolve().parents[1]
CATALOG = json.loads((ROOT / 'Resources/Localization/Localizable.json').read_text())
STRINGS = CATALOG['strings']
LANGS = [code for code in CATALOG['languages'] if code != 'zh-Hans']
CJK = re.compile(r'[一-鿿]')
# English upstream names stay untranslated in every language.
PROTECTED = ['Session', 'Weekly', 'Extra Usage', 'Premium', 'Credits', 'Token Plan', 'Coding Plan', 'MCP',
             'Claude', 'Codex', 'Kimi', 'GLM', 'Copilot', 'Antigravity', 'Cursor', 'MiniMax', 'Windsurf', 'Kiro',
             'OpenCode Go', 'ClinePass', 'Gemini', 'GitHub', 'BigModel', 'Z.ai', 'AI Monitor']
# Source text that is matched or replaced in code, never displayed by itself.
NOT_KEYS = {'简体中文', '繁體中文', '日本語', ' · 计费周期', '当前 '}
PATTERNS = [(key, re.compile('^' + re.sub(r'\\\{\d\\\}', '(.+?)', re.escape(key)) + '$', re.S))
            for key in STRINGS if '{0}' in key]


def whole(text):
    if text in STRINGS or not CJK.search(text):
        return True
    if any(regex.match(text) and all(covered(g) for g in regex.match(text).groups()) for _, regex in PATTERNS):
        return True
    # A "（qualifier）" suffix, alone or after a known base, as L10n.whole() handles it.
    match = re.fullmatch(r'(.*)（(.+)）', text, re.S)
    return bool(match) and match.group(2) in STRINGS and (not match.group(1) or whole(match.group(1)))


def covered(text):
    """Mirror of L10n.translate: exact, template, ' · ' segments or whole sentences."""
    if whole(text):
        return True
    if ' · ' in text and all(whole(part) for part in text.split(' · ')):
        return True
    sentences = [s + '。' for s in text.split('。') if s]
    return len(sentences) > 1 and ''.join(sentences) == text and all(whole(s) for s in sentences)


def swift_sources():
    for path in sorted((ROOT / 'Sources').rglob('*.swift')):
        if path.name != 'UIInteractionChecks.swift':
            yield path, path.read_text()


def swift_texts():
    found = set()
    for path, text in swift_sources():
        for line in text.splitlines():
            if line.strip().startswith('//'):
                continue
            for raw in re.findall(r'"((?:[^"\\\n]|\\.)*)"', line) + re.findall(r'(?:L10n\.tr|say)\("([^"\n]+)"', line):
                # Swift interpolation becomes the same {n} template the code passes to L10n.
                parts = re.split(r'\\\((?:[^()]|\([^()]*\))*\)', raw)
                value = ''.join(p + ('{%d}' % i if i < len(parts) - 1 else '') for i, p in enumerate(parts))
                if CJK.search(value) and value not in NOT_KEYS and '\\(' not in value:
                    found.add((path.name, value))
    return found


def collector_texts():
    found = set()
    for path in sorted((ROOT / 'collector').glob('*.py')):
        for line in path.read_text().splitlines():
            if line.strip().startswith('#'):
                continue
            for a, b in re.findall(r"'((?:[^'\\\n]|\\.)*)'|\"((?:[^\"\\\n]|\\.)*)\"", line):
                value = (a or b).replace('%d', '{0}').replace('%g', '{0}').replace('%s', '{0}')
                if CJK.search(value):
                    found.add((path.name, value.strip(' ·')))
    return found


class CatalogTests(unittest.TestCase):
    def test_every_language_is_complete(self):
        self.assertEqual(LANGS, ['zh-Hant', 'en', 'ja', 'ko', 'es', 'fr', 'de', 'pt-BR'])
        for key, row in STRINGS.items():
            self.assertEqual(set(row), set(LANGS), key)
            for code, value in row.items():
                self.assertTrue(value.strip(), (key, code))

    def test_placeholders_match(self):
        for key, row in STRINGS.items():
            expected = sorted(set(re.findall(r'\{\d\}', key)))
            for code, value in row.items():
                self.assertEqual(sorted(set(re.findall(r'\{\d\}', value))), expected, (key, code))

    def test_english_upstream_terms_are_kept(self):
        for key, row in STRINGS.items():
            for term in PROTECTED:
                if term in key:
                    for code, value in row.items():
                        self.assertIn(term, value, (key, code, term))

    def test_non_chinese_translations_leave_no_chinese(self):
        for key, row in STRINGS.items():
            for code in ('en', 'ko', 'es', 'fr', 'de', 'pt-BR'):
                self.assertIsNone(CJK.search(row[code]), (key, code))

    def test_login_script_messages_are_shell_quoted(self):
        # Translations may contain apostrophes; the login script must quote, never format, them.
        text = (ROOT / 'Sources/MonitorShared/MonitorStore.swift').read_text()
        self.assertIn('''printf '%s\\\\n' '" + L10n.tr(key).replacingOccurrences(of: "'", with: "'\\\\''")''', text)

    def test_every_swift_display_string_is_translatable(self):
        missing = sorted(value for _, value in swift_texts() if not covered(value))
        self.assertEqual(missing, [])

    def test_every_collector_message_is_translatable(self):
        missing = sorted(value for _, value in collector_texts() if not covered(value))
        self.assertEqual(missing, [])

    def test_views_do_not_show_untranslated_literals(self):
        # SwiftUI shows String arguments verbatim; Chinese literals must pass through L10n.
        for name in ('QuotaPanel.swift', 'SettingsPanel.swift', 'MiniMaxConnectionEditor.swift', 'Interaction.swift'):
            text = (ROOT / 'Sources/MonitorShared' / name).read_text()
            for call in ('Text("', 'Button("', '.help("', 'Picker("', 'Label("', 'confirmationDialog("'):
                for match in re.finditer(re.escape(call) + r'([^"\n]*)"', text):
                    self.assertIsNone(CJK.search(match.group(1)), (name, match.group(0)))

    def test_catalog_is_bundled(self):
        build = (ROOT / 'scripts/build.py').read_text()
        self.assertIn("Resources/Localization/Localizable.json", build)
        self.assertIn("'Localization'", (ROOT / 'scripts/verify_bundle.py').read_text())


if __name__ == '__main__':
    unittest.main()
