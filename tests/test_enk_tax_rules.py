"""Legal examples/boundaries for the reused Norwegian a/d tax rules."""
import importlib.util
from pathlib import Path
import sys
import unittest
from datetime import date
from decimal import Decimal as D

path=Path(__file__).resolve().parents[1]/'apps/erpnext_norway/erpnext_norway/enk_tax_rules.py'
spec=importlib.util.spec_from_file_location('enk_tax_rules',path)
r=importlib.util.module_from_spec(spec);sys.modules[spec.name]=r;spec.loader.exec_module(r)

class TaxPoolTest(unittest.TestCase):
    def calc(self,group='a',**kw):
        return r.calculate_saldo_pool(group=r.SaldoGroup(group),year_end=date(2026,12,31),
            opening_balance=D(kw.pop('opening','0')),**{k:D(v) if isinstance(v,str) else v for k,v in kw.items()})

    def test_annual_acquisition_and_pooling(self):
        # Full annual rate even when native December source is late in the year.
        a=self.calc(acquisitions='100000')
        self.assertEqual((a.depreciation_deduction,a.closing_balance),(D('30000'),D('70000')))
        d=self.calc('d',opening='70000',acquisitions='50000',disposal_proceeds='20000')
        self.assertEqual((d.depreciation_deduction,d.closing_balance),(D('20000'),D('80000')))

    def test_positive_small_balance_is_optional_and_strict(self):
        self.assertEqual(self.calc(opening='29999').depreciation_deduction,D('8999.7'))
        self.assertEqual(self.calc(opening='29999',write_off_small_positive_balance=True).closing_balance,0)
        with self.assertRaises(r.RuleValidationError):self.calc(opening='30000',write_off_small_positive_balance=True)
        self.assertEqual(self.calc(opening='30000').closing_balance,D('21000'))

    def test_negative_small_balance_is_mandatory_and_strict(self):
        self.assertEqual(self.calc(opening='-29999').negative_balance_income,D('29999'))
        result=self.calc(opening='-30000')
        self.assertEqual((result.negative_balance_income,result.closing_balance),(D('9000'),D('-21000')))
        result=self.calc('d',opening='10000',disposal_proceeds='110000')
        self.assertEqual((result.negative_balance_income,result.closing_balance),(D('20000'),D('-80000')))

    def test_optional_income_and_lower_depreciation(self):
        result=self.calc(opening='100000',disposal_proceeds='20000',disposal_proceeds_taken_to_income='5000',requested_depreciation='10000')
        self.assertEqual((result.depreciation_deduction,result.closing_balance),(D('10000'),D('75000')))
        result=self.calc(opening='-100000',additional_negative_balance_income='70000')
        self.assertEqual((result.negative_balance_income,result.closing_balance),(D('100000'),0))
        for kw in [dict(opening='100',requested_depreciation='31'),dict(opening='-30000',additional_negative_balance_income='21001'),
                dict(disposal_proceeds='1',disposal_proceeds_taken_to_income='2'),dict(opening='0',requested_depreciation='1')]:
            with self.subTest(kw=kw),self.assertRaises(r.RuleValidationError):self.calc(**kw)

    def test_nonfinite_and_unqualified_year_are_not_silent(self):
        with self.assertRaises(r.RuleValidationError):self.calc(opening='NaN')
        with self.assertRaises(r.RuleValidationError):r.calculate_saldo_pool(group=r.SaldoGroup.A,year_end=date(2027,12,31),opening_balance=D(0))
