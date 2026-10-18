import csv
import hashlib
import io
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from build_norway_chart import RESOURCE, render, source_accounts


class NativeChartData(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = source_accounts()
        cls.csv = render()
        cls.rows = list(csv.DictReader(io.StringIO(cls.csv)))
        cls.accounts = {row["Account Number"]: row for row in cls.rows if row["Account Number"]}

    def test_pinned_original_and_complete_unmodified_number_label_pairs(self):
        self.assertEqual(hashlib.sha256((RESOURCE / "upstream/account.account-no.csv").read_bytes()).hexdigest(),
                         "32cc49b9aa195622a83367f867564fff0819bed608cffa398dfe0ddd9875161b")
        self.assertEqual(len(self.accounts), 745)
        self.assertEqual({code: row["Account Name"] for code, row in self.accounts.items()},
                         {row["code"]: row["name@nb_NO"] for row in self.source})
        self.assertEqual((RESOURCE / "norway.csv").read_text(), self.csv)

    def test_groups_resolve_and_all_native_root_types_are_present(self):
        groups = {row["Account Name"] for row in self.rows if row["Is Group"] == "1"}
        self.assertEqual({row["Root Type"] for row in self.rows if not row["Parent Account"]},
                         {"Asset", "Liability", "Equity", "Income", "Expense"})
        self.assertTrue(all(not row["Parent Account"] or row["Parent Account"] in groups for row in self.rows))

    def test_native_reskontro_defaults_and_tax_settlement_are_not_confused(self):
        self.assertEqual({code for code, row in self.accounts.items() if row["Account Type"] == "Payable"}, {"2400"})
        self.assertEqual({code for code, row in self.accounts.items() if row["Account Type"] == "Receivable"}, {"1500"})
        self.assertEqual(self.accounts["2740"]["Account Type"], "Tax")
        self.assertEqual(self.accounts["1570"]["Account Type"], "")
        self.assertEqual(self.accounts["2070"]["Root Type"], "Equity")

    def test_native_income_and_expense_groups_retain_financial_meaning(self):
        self.assertEqual(self.accounts["8050"]["Root Type"], "Income")
        self.assertEqual(self.accounts["8060"]["Root Type"], "Income")
        self.assertEqual(self.accounts["8160"]["Root Type"], "Expense")
        self.assertNotEqual(self.accounts["1470"]["Account Type"], "Stock")
        self.assertEqual(self.accounts["1460"]["Account Type"], "Stock")


if __name__ == "__main__":
    unittest.main()
