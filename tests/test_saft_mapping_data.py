"""Validate reused classifications against the shipped chart and official codes."""
import csv
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'apps/erpnext_norway/erpnext_norway/saft_data'

class MappingDataTest(unittest.TestCase):
    def test_exact_shipped_account_identities_and_official_groups(self):
        with (ROOT/'resources/norway-chart/norway.csv').open() as f:
            chart={r['Account Number']:r for r in csv.DictReader(f) if r['Is Group']=='0'}
        with (DATA/'naeringsspesifikasjon-2025-2026.csv').open(encoding='utf-8-sig') as f:
            valid={(r['GroupingCategory'],r['GroupingCode']) for r in csv.DictReader(f,delimiter=';')}
        with (DATA/'account-mapping.csv').open() as f:
            rows=list(csv.DictReader(f,delimiter=';'))
        self.assertEqual(len(rows),357)
        self.assertEqual(len({r['account_number'] for r in rows}),len(rows))
        for r in rows:
            with self.subTest(account=r['account_number']):
                c=chart[r['account_number']]
                self.assertEqual((r['label'],r['root_type']),(c['Account Name'],c['Root Type']))
                self.assertIn((r['GroupingCategory'],r['GroupingCode']),valid)
