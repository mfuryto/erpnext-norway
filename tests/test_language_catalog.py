"""Translation resource integrity, including contextual price/tax meanings."""
import csv
from collections import Counter
from pathlib import Path
import re
import unittest

CATALOG = Path(__file__).resolve().parents[1] / 'apps/erpnext_norway/erpnext_norway/translations/nb.csv'


class LanguageCatalog(unittest.TestCase):
    def test_catalog_preserves_keys_placeholders_and_contexts(self):
        entries = {}
        with CATALOG.open() as stream:
            rows = list(csv.reader(stream))
        for row in rows:
            self.assertIn(len(row), (2, 3))
            source, target = row[:2]
            context = row[2] if len(row) == 3 else ''
            self.assertTrue(source and target)
            self.assertNotIn((source, context), entries)
            entries[source, context] = target
            self.assertEqual(Counter(re.findall(r'\{[^{}]+\}', source)),
                             Counter(re.findall(r'\{[^{}]+\}', target)), source)
            if 'https://docs.frappe.io' in source:
                self.assertEqual(re.findall(r'\]\(([^)]+)\)', source),
                                 re.findall(r'\]\(([^)]+)\)', target), source)
        self.assertEqual(entries['Warehouse', ''], 'Lager')
        self.assertEqual(entries['Serial & Batch', ''], 'Serienumre og partier')
        self.assertEqual(entries['Norway', ''], 'Norge')
        self.assertEqual(entries['VAT', ''], 'MVA')
        self.assertEqual(entries['Value Added Tax', ''], 'Merverdiavgift')
        self.assertNotIn(('Rate', ''), entries)
        self.assertNotIn(('Tax', ''), entries)
        self.assertEqual(entries['Rate', 'Item Price'], 'Enhetspris')
        self.assertEqual(entries['Submit', ''], 'Send inn')
        self.assertEqual(entries['Payment Reconciliation', ''], 'Betalingsavstemming')
        self.assertEqual(entries['Accounts Setup', ''], 'Regnskapsoppsett')
        self.assertEqual(entries['{0} of {1} steps done', ''], '{0} av {1} trinn fullført')
