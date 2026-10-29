# Upstream MIT test vectors: ENK Norge at 94406e542ed991a8de237b9de44b8d1dd576b566.
# Copyright (c) 2026 Haakon Fornes; app saft_data/LICENSE.enk-norge.
from dataclasses import replace
from datetime import date
from decimal import Decimal
from unittest import TestCase

from lxml import etree

from erpnext_norway.saft_builder import (
	NS,
	AccountData,
	AccountMapping,
	CompanyData,
	LedgerEntry,
	PartyData,
	SaftExportData,
	SaftExportError,
	TaxMapping,
	build_saf_t,
	validate_saf_t,
)


class TestSaftBuilder(TestCase):
	def export_data(self):
		return SaftExportData(
			company=CompanyData("999999999", "Eksempel ENK", "90000000", "Gate 1", "0001", "Oslo"),
			period_start=date(2026, 1, 1),
			period_end=date(2026, 1, 31),
			software_company_name="Frappe Technologies Pvt. Ltd.",
			software_id="ERPNext with enk_norge",
			software_version="16.0.0",
			accounts={
				"Bank": AccountData("Bank", "Bankinnskudd"),
				"Revenue": AccountData("Revenue", "Konsulentinntekt"),
				"Receivable": AccountData("Receivable", "Kundefordringer"),
			},
			account_mappings={
				"Bank": AccountMapping("1920", "balanseverdiForOmloepsmiddel", "1920"),
				"Revenue": AccountMapping("3000", "salgsinntekt", "3000"),
				"Receivable": AccountMapping("1500", "balanseverdiForOmloepsmiddel", "1500"),
			},
			entries=(
				LedgerEntry("GL-OPEN-1", "Bank", Decimal("100.00"), Decimal(), date(2025, 12, 31), "Journal Entry", "OPEN"),
				LedgerEntry("GL-OPEN-2", "Revenue", Decimal(), Decimal("100.00"), date(2025, 12, 31), "Journal Entry", "OPEN"),
				LedgerEntry("GL-1", "Receivable", Decimal("1250.00"), Decimal(), date(2026, 1, 15), "Sales Invoice", "SINV-1", party_type="Customer", party="CUST-1", reference_number="SINV-1"),
				LedgerEntry("GL-2", "Revenue", Decimal(), Decimal("1250.00"), date(2026, 1, 15), "Sales Invoice", "SINV-1", reference_number="SINV-1"),
			),
			parties={("Customer", "CUST-1"): PartyData("Customer", "CUST-1", "Kunde AS", "987654321", "NO")},
			created_date=date(2026, 2, 1),
		)

	def test_builds_xsd_valid_xml_with_balances_and_references(self):
		xml = build_saf_t(self.export_data())
		validate_saf_t(xml)
		root = etree.fromstring(xml)
		ns = {"s": NS}
		self.assertEqual(root.xpath("string(.//s:GeneralLedgerEntries/s:NumberOfEntries)", namespaces=ns), "1")
		self.assertEqual(root.xpath("string(.//s:GeneralLedgerEntries/s:TotalDebit)", namespaces=ns), "1250.00")
		self.assertEqual(root.xpath("string(.//s:GeneralLedgerEntries/s:TotalCredit)", namespaces=ns), "1250.00")
		self.assertEqual(root.xpath("string(.//s:Account[s:AccountID='1920']/s:OpeningDebitBalance)", namespaces=ns), "100.00")
		self.assertEqual(root.xpath("string(.//s:Account[s:AccountID='1500']/s:ClosingDebitBalance)", namespaces=ns), "1250.00")
		self.assertEqual(root.xpath("string(.//s:Customer/s:CustomerID)", namespaces=ns), "CUST-1")
		self.assertEqual(root.xpath("string(.//s:Line[s:RecordID='GL-1']/s:ReferenceNumber)", namespaces=ns), "SINV-1")

	def test_rejects_missing_required_account_mapping(self):
		data = self.export_data()
		data = SaftExportData(**{**data.__dict__, "account_mappings": {**data.account_mappings, "Revenue": AccountMapping("3000", "", "")}})
		with self.assertRaisesRegex(SaftExportError, "grouping category"):
			build_saf_t(data)

	def test_rejects_unbalanced_voucher(self):
		data = self.export_data()
		entries = data.entries[:-1]
		data = SaftExportData(**{**data.__dict__, "entries": entries})
		with self.assertRaisesRegex(SaftExportError, "SINV-1 balanserer ikke"):
			build_saf_t(data)

	def test_rejects_duplicate_saf_t_account_id(self):
		data = self.export_data()
		data = replace(
			data,
			account_mappings={
				**data.account_mappings,
				"Revenue": AccountMapping("1920", "salgsinntekt", "3000"),
			},
		)
		with self.assertRaisesRegex(SaftExportError, "må være unik"):
			build_saf_t(data)

	def test_emits_mva_mapping_and_information(self):
		data = self.export_data()
		entries = list(data.entries)
		entries[3] = replace(entries[3], credit=Decimal("1000.00"))
		entries.append(LedgerEntry(
			"GL-3", "Output VAT", Decimal(), Decimal("250.00"), date(2026, 1, 15),
			"Sales Invoice", "SINV-1", tax_code="OUT25", tax_base=Decimal("1000.00"),
		))
		data = replace(
			data,
			accounts={**data.accounts, "Output VAT": AccountData("Output VAT", "Utgående MVA")},
			account_mappings={
				**data.account_mappings,
				"Output VAT": AccountMapping("2740", "kortsiktigGjeld", "2740"),
			},
			entries=tuple(entries),
			tax_mappings={"OUT25": TaxMapping("OUT25", Decimal("25"), "3")},
		)
		root = etree.fromstring(build_saf_t(data))
		ns = {"s": NS}
		self.assertEqual(root.xpath("string(.//s:TaxCodeDetails/s:StandardTaxCode)", namespaces=ns), "3")
		self.assertEqual(root.xpath("string(.//s:Line[s:RecordID='GL-3']/s:TaxInformation/s:TaxBase)", namespaces=ns), "1000.00")


class TestNorwegianBuilderExtensions(TestCase):
    export_data = TestSaftBuilder.export_data
    def test_native_opening_excluded_from_movements(self):
        data = self.export_data()
        entries = tuple(replace(r, posting_date=date(2026, 1, 1), is_opening=True)
                        if r.voucher_no == "OPEN" else r for r in data.entries)
        root = etree.fromstring(build_saf_t(replace(data, entries=entries)))
        ns = {"s": NS}
        self.assertEqual(root.xpath("string(.//s:NumberOfEntries)", namespaces=ns), "1")
        self.assertEqual(root.xpath("string(.//s:Account[s:AccountID='1920']/s:OpeningDebitBalance)", namespaces=ns), "100.00")

    def test_zero_amount_and_multiple_base_rates(self):
        from erpnext_norway.saft_builder import TaxInformation
        data = self.export_data()
        entries = tuple(replace(r, tax_information=(TaxInformation("0", Decimal(0), Decimal(0)),))
                        if r.record_id == "GL-2" else r for r in data.entries)
        root = etree.fromstring(build_saf_t(replace(data, entries=entries,
            tax_mappings={"0": TaxMapping("0", Decimal(0), "0", (Decimal(0), Decimal(60), Decimal(100)))})))
        ns = {"s": NS}
        self.assertEqual(root.xpath(".//s:TaxCodeDetails/s:BaseRate/text()", namespaces=ns), ["0.00", "60.00", "100.00"])
        self.assertEqual(root.xpath("string(.//s:TaxInformation/s:CreditTaxAmount/s:Amount)", namespaces=ns), "0.00")

    def test_foreign_currency_precision(self):
        data = self.export_data()
        entries = tuple(replace(r, currency_code="EUR", currency_amount=Decimal("125.0000000001"))
                        if r.record_id == "GL-1" else r for r in data.entries)
        root = etree.fromstring(build_saf_t(replace(data, entries=entries)))
        self.assertEqual(root.xpath("string(.//s:CurrencyAmount)", namespaces={"s": NS}), "125.0000000001")

    def test_native_dimensions_and_fractional_base_rate(self):
        from erpnext_norway.saft_builder import TaxInformation
        data=self.export_data()
        entries=tuple(replace(r, analyses=(("CC","Main"),("PROJECT","P1")),
            tax_information=(TaxInformation("1",Decimal("1250"),Decimal("100")),))
            if r.record_id=="GL-1" else r for r in data.entries)
        root=etree.fromstring(build_saf_t(replace(data,entries=entries,
            analysis_catalog={("CC","Main"):("Kostnadssted","Main"),("PROJECT","P1"):("Prosjekt","Project1")},
            tax_mappings={"1":TaxMapping("1",Decimal(25),"1",(Decimal("60.123456"),))})))
        ns={"s":NS}
        self.assertEqual(root.xpath('.//s:Analysis/s:AnalysisID/text()',namespaces=ns),["Main","P1"])
        self.assertEqual(root.xpath('string(.//s:BaseRate)',namespaces=ns),"60.123456")

    def test_source_nok_amount_is_not_silently_rounded(self):
        data=self.export_data()
        entries=tuple(replace(r,debit=Decimal("1250.001")) if r.record_id=="GL-1" else r for r in data.entries)
        with self.assertRaisesRegex(SaftExportError,"hele øre"):
            build_saf_t(replace(data,entries=entries))


    def test_reverse_charge_tax_direction_can_differ_from_basis(self):
        from erpnext_norway.saft_builder import TaxInformation
        data=self.export_data()
        for credit, direction in [(True, "CreditTaxAmount"), (False, "DebitTaxAmount")]:
            entries=tuple(replace(r,tax_information=(TaxInformation("86",Decimal("1250"),Decimal("100"),credit),))
                if r.record_id=="GL-1" else r for r in data.entries)
            root=etree.fromstring(build_saf_t(replace(data,entries=entries,
                tax_mappings={"86":TaxMapping("86",Decimal(25),"86",(Decimal(60),))})))
            self.assertEqual(root.xpath("string(.//s:TaxInformation/s:"+direction+"/s:Amount)",namespaces={"s":NS}),"100.00")


if __name__ == '__main__':
    import unittest
    unittest.main()
