"""Claude extra-usage values below are synthetic protocol fixtures, not live balances."""
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'collector'))
from other_providers import parse_claude

class ExtraUsageTests(unittest.TestCase):
    def parse(self, **fields):
        return parse_claude({'extra_usage': dict(is_enabled=True, **fields)})
    def test_cents_become_dollars(self):
        rows = self.parse(monthly_limit=3000, used_credits=0)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['remaining'], 30)
        self.assertEqual(rows[0]['limit'], 30)
        self.assertEqual(rows[0]['remainingPercent'], 100)
        self.assertEqual(rows[0]['currency'], 'USD')
        self.assertEqual(rows[0]['kind'], 'extra')
        self.assertIsNone(rows[0]['durationMinutes'])
    def test_partly_used_budget(self):
        row = self.parse(monthly_limit=3000, used_credits=750)[0]
        self.assertEqual(row['remaining'], 22.5)
        self.assertEqual(row['remainingPercent'], 75)
    def test_over_budget_is_zero_not_negative(self):
        row = self.parse(monthly_limit=3000, used_credits=4000)[0]
        self.assertEqual(row['remainingPercent'], 0)
        self.assertEqual(row['remaining'], 0)
    def test_missing_limit_not_fabricated(self):
        self.assertEqual(self.parse(used_credits=0), [])
    def test_missing_consumption_not_fabricated(self):
        self.assertEqual(self.parse(monthly_limit=3000), [])
    def test_disabled_not_shown(self):
        self.assertEqual(parse_claude({'extra_usage': {'is_enabled':False,'monthly_limit':3000,'used_credits':0}}), [])
    def test_zero_limit_not_unlimited(self):
        self.assertEqual(self.parse(monthly_limit=0, used_credits=0), [])
    def test_extra_does_not_replace_regular_windows(self):
        rows = parse_claude({'five_hour': {'utilization':0}, 'seven_day': {'utilization':75},
                            'extra_usage': {'is_enabled':True,'monthly_limit':3000,'used_credits':0}})
        self.assertEqual([r['id'] for r in rows], ['five_hour','seven_day','extra_usage'])

if __name__ == '__main__': unittest.main()
