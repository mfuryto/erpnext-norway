# Adapted from enk_norge/saft.py at 94406e542ed991a8de237b9de44b8d1dd576b566.
# Copyright (c) 2026 Haakon Fornes. MIT; see saft_data/LICENSE.enk-norge.
"""Norsk SAF-T Financial 1.40-eksport.

Byggeren tar bare vanlige Python-datastrukturer. Frappe-adapteren nederst er bevisst
tynn, slik at regnskapslogikken kan testes uten database eller nettsted.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from lxml import etree

NS = "urn:StandardAuditFile-Taxation-Financial:NO"
XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"
SCHEMA_VERSION = "1.40"
SCHEMA_FILENAME = "Norwegian_SAF-T_Financial_Schema_v_1.40.xsd"
SCHEMA_PATH = Path(__file__).with_name("saft_data") / SCHEMA_FILENAME
MONEY_QUANTUM = Decimal("0.01")

# Kodene er de aktuelle, offentlige SAF-T-standardavgiftskodene for appens
# avgrensede norske behandlinger. Andre avgiftsbehandlinger stoppes eksplisitt.
OUTPUT_TAX_CODES = {
	"Domestic 25": ("3", Decimal("25")),
	"Domestic 15": ("31", Decimal("15")),
	"Domestic 12": ("33", Decimal("12")),
}
INPUT_TAX_CODES = {
	Decimal("25"): ("1", Decimal("25")),
	Decimal("15"): ("11", Decimal("15")),
	Decimal("12"): ("13", Decimal("12")),
}


class SaftExportError(ValueError):
	"""Eksporten mangler data eller kan ikke avstemmes."""


@dataclass(frozen=True)
class CompanyData:
	registration_number: str
	name: str
	telephone: str
	street_name: str | None = None
	postal_code: str | None = None
	city: str | None = None
	country: str = "NO"
	currency: str = "NOK"
	vat_registration_number: str | None = None
	vat_registration_date: date | None = None
	bank_account_number: str | None = None
	address_line2: str | None = None


@dataclass(frozen=True)
class AccountMapping:
	account_id: str
	grouping_category: str
	grouping_code: str


@dataclass(frozen=True)
class AccountData:
	name: str
	description: str
	created_date: date | None = None


@dataclass(frozen=True)
class PartyData:
	party_type: str
	party_id: str
	name: str
	registration_number: str | None = None
	country: str | None = None
	street_name: str | None = None
	postal_code: str | None = None
	city: str | None = None
	address_line2: str | None = None


@dataclass(frozen=True)
class TaxMapping:
	code: str
	percentage: Decimal
	standard_tax_code: str
	base_rates: tuple[Decimal, ...] = (Decimal("100"),)


@dataclass(frozen=True)
class TaxInformation:
	code: str
	tax_base: Decimal | None = None
	tax_amount: Decimal | None = None
	tax_credit: bool | None = None


@dataclass(frozen=True)
class LedgerEntry:
	record_id: str
	account: str
	debit: Decimal
	credit: Decimal
	posting_date: date
	voucher_type: str
	voucher_no: str
	remarks: str = ""
	transaction_date: date | None = None
	system_entry_date: date | None = None
	modified_date: date | None = None
	party_type: str | None = None
	party: str | None = None
	due_date: date | None = None
	reference_number: str | None = None
	tax_code: str | None = None
	tax_base: Decimal | None = None
	tax_information: tuple[TaxInformation, ...] = ()
	is_opening: bool = False
	currency_code: str | None = None
	currency_amount: Decimal | None = None
	analyses: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class SaftExportData:
	company: CompanyData
	period_start: date
	period_end: date
	software_company_name: str
	software_id: str
	software_version: str
	accounts: dict[str, AccountData]
	account_mappings: dict[str, AccountMapping]
	entries: tuple[LedgerEntry, ...]
	parties: dict[tuple[str, str], PartyData] = field(default_factory=dict)
	tax_mappings: dict[str, TaxMapping] = field(default_factory=dict)
	created_date: date = field(default_factory=date.today)
	analysis_catalog: dict[tuple[str, str], tuple[str, str]] = field(default_factory=dict)


def _money(value: Decimal) -> Decimal:
	return Decimal(value).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)


def _text(value: Decimal | date | datetime | str | int) -> str:
	if isinstance(value, Decimal):
		return f"{_money(value):.2f}"
	if isinstance(value, datetime):
		return value.date().isoformat()
	if isinstance(value, date):
		return value.isoformat()
	return str(value)


def _element(parent: etree._Element, name: str, value: Decimal | date | datetime | str | int) -> etree._Element:
	element = etree.SubElement(parent, f"{{{NS}}}{name}")
	if name in {"BaseRate", "TaxPercentage"} and isinstance(value, Decimal):
		# Percentage precision is not the monetary two-decimal constraint.
		text = format(value, "f")
		if "." not in text:
			text += ".00"
		elif len(text.rsplit(".", 1)[1]) < 2:
			text += "0"
		element.text = text
	else:
		element.text = _text(value)
	return element


def _balance(parent: etree._Element, prefix: str, value: Decimal) -> None:
	value = _money(value)
	name = f"{prefix}DebitBalance" if value >= 0 else f"{prefix}CreditBalance"
	_element(parent, name, abs(value))


def _entry_balance(entries: Iterable[LedgerEntry]) -> Decimal:
	return sum((_money(entry.debit) - _money(entry.credit) for entry in entries), Decimal())


def _require(condition: bool, message: str) -> None:
	if not condition:
		raise SaftExportError(message)


def _validate_input(data: SaftExportData) -> None:
	_require(data.period_start <= data.period_end, "Fra-dato kan ikke være etter til-dato.")
	_require(data.company.registration_number, "SAF-T krever organisasjonsnummer.")
	_require(data.company.name, "SAF-T krever foretaksnavn.")
	_require(data.company.telephone, "SAF-T 1.40 krever telefonnummer for foretaket.")
	_require(data.company.currency == "NOK", "Denne eksporten støtter foreløpig bare NOK som hovedvaluta.")

	for entry in data.entries:
		_require(entry.account in data.accounts, f"Mangler kontodata for {entry.account}.")
		mapping = data.account_mappings.get(entry.account)
		_require(mapping is not None, f"Mangler SAF-T-mapping for konto {entry.account}.")
		_require(mapping.account_id, f"Mangler SAF-T-konto-ID for {entry.account}.")
		_require(mapping.grouping_category, f"Mangler SAF-T grouping category for {entry.account}.")
		_require(mapping.grouping_code, f"Mangler SAF-T grouping code for {entry.account}.")
		debit, credit = _money(entry.debit), _money(entry.credit)
		_require(entry.debit == debit and entry.credit == credit, "SAF-T krever hovedboksbeløp i hele øre; kildedata blir ikke avrundet ved eksport.")
		_require((debit > 0) != (credit > 0), f"Bilagslinje {entry.record_id} må ha enten debet eller kredit.")
		if entry.party_type or entry.party:
			_require(
				entry.party_type in ("Customer", "Supplier") and bool(entry.party),
				f"Bilagslinje {entry.record_id} har en part som SAF-T-eksporten ikke støtter.",
			)
			_require(
				(entry.party_type, entry.party) in data.parties,
				f"Mangler kunde- eller leverandørdata for {entry.party_type} {entry.party}.",
			)
		for analysis in entry.analyses:
			_require(analysis in data.analysis_catalog, f"Mangler dimensjonsdata for {analysis}.")
		for tax_information in entry.tax_information or ((TaxInformation(entry.tax_code, entry.tax_base),) if entry.tax_code else ()):
			_require(tax_information.code in data.tax_mappings, f"Mangler SAF-T MVA-mapping for {tax_information.code}.")
			if tax_information.tax_amount is not None:
				_require(tax_information.tax_amount >= 0, f"MVA-beløp må være null eller positivt for {tax_information.code}.")
	for mapping in data.tax_mappings.values():
		_require(mapping.code, "En SAF-T MVA-mapping mangler avgiftskode.")
		_require(mapping.standard_tax_code, f"MVA-mapping {mapping.code} mangler standard avgiftskode.")
	used_account_ids = [
		data.account_mappings[account].account_id
		for account in {entry.account for entry in data.entries}
	]
	_require(
		len(used_account_ids) == len(set(used_account_ids)),
		"SAF-T-konto-ID må være unik. Bruk ERPNext-kontonummeret, ikke en delt standardkonto.",
	)

	period_entries = [entry for entry in data.entries if not entry.is_opening and data.period_start <= entry.posting_date <= data.period_end]
	for voucher, voucher_entries in _group_vouchers(period_entries).items():
		if _entry_balance(voucher_entries) != Decimal():
			raise SaftExportError(f"Bilag {voucher[1]} balanserer ikke.")


def _group_vouchers(entries: Iterable[LedgerEntry]) -> dict[tuple[str, str, date], list[LedgerEntry]]:
	vouchers: dict[tuple[str, str, date], list[LedgerEntry]] = defaultdict(list)
	for entry in entries:
		vouchers[(entry.voucher_type, entry.voucher_no, entry.posting_date)].append(entry)
	return vouchers


def _add_company(parent: etree._Element, company: CompanyData) -> None:
	_element(parent, "RegistrationNumber", company.registration_number)
	_element(parent, "Name", company.name)
	if company.street_name or company.postal_code or company.city:
		address = etree.SubElement(parent, f"{{{NS}}}Address")
		if company.street_name:
			_element(address, "StreetName", company.street_name)
		if company.address_line2:
			_element(address, "AdditionalAddressDetail", company.address_line2)
		if company.city:
			_element(address, "City", company.city)
		if company.postal_code:
			_element(address, "PostalCode", company.postal_code)
		_element(address, "Country", company.country)
	contact = etree.SubElement(parent, f"{{{NS}}}Contact")
	contact_person = etree.SubElement(contact, f"{{{NS}}}ContactPerson")
	_element(contact_person, "FirstName", "NotUsed")
	_element(contact_person, "LastName", company.name)
	_element(contact, "Telephone", company.telephone)
	if company.vat_registration_number:
		registration = etree.SubElement(parent, f"{{{NS}}}TaxRegistration")
		_element(registration, "TaxRegistrationNumber", company.vat_registration_number)
		_element(registration, "TaxAuthority", "Skatteetaten")
		if company.vat_registration_date:
			_element(registration, "TaxVerificationDate", company.vat_registration_date)
	if company.bank_account_number:
		account = etree.SubElement(parent, f"{{{NS}}}BankAccount")
		_element(account, "BankAccountNumber", company.bank_account_number)


def _add_party(parent: etree._Element, party: PartyData, entries: Iterable[LedgerEntry], data: SaftExportData) -> None:
	if party.registration_number:
		_element(parent, "RegistrationNumber", party.registration_number)
	_element(parent, "Name", party.name)
	if party.country or party.street_name or party.city or party.postal_code:
		address = etree.SubElement(parent, f"{{{NS}}}Address")
		for tag, value in (("StreetName", party.street_name), ("AdditionalAddressDetail", party.address_line2),
				("City", party.city), ("PostalCode", party.postal_code), ("Country", party.country)):
			if value:
				_element(address, tag, value)
	_element(parent, "CustomerID" if party.party_type == "Customer" else "SupplierID", party.party_id)

	by_account: dict[str, list[LedgerEntry]] = defaultdict(list)
	for entry in entries:
		if entry.party_type == party.party_type and entry.party == party.party_id:
			by_account[entry.account].append(entry)
	for account, party_entries in by_account.items():
		balance_account = etree.SubElement(parent, f"{{{NS}}}BalanceAccount")
		_element(balance_account, "AccountID", data.account_mappings[account].account_id)
		opening = _entry_balance(entry for entry in party_entries if (entry.posting_date < data.period_start or entry.is_opening))
		closing = _entry_balance(entry for entry in party_entries if entry.posting_date <= data.period_end)
		_balance(balance_account, "Opening", opening)
		_balance(balance_account, "Closing", closing)


def _add_tax_information(line: etree._Element, entry: LedgerEntry, information: TaxInformation, mapping: TaxMapping) -> None:
	tax = etree.SubElement(line, f"{{{NS}}}TaxInformation")
	_element(tax, "TaxType", "MVA")
	_element(tax, "TaxCode", mapping.code)
	_element(tax, "TaxPercentage", mapping.percentage)
	_element(tax, "Country", "NO")
	if information.tax_base is not None:
		_element(tax, "TaxBase", information.tax_base)
	amount = information.tax_amount if information.tax_amount is not None else (_money(entry.debit) if _money(entry.debit) else _money(entry.credit))
	credit = information.tax_credit if information.tax_credit is not None else not bool(_money(entry.debit))
	amount_element = etree.SubElement(tax, f"{{{NS}}}{'CreditTaxAmount' if credit else 'DebitTaxAmount'}")
	_element(amount_element, "Amount", amount)


def build_saf_t(data: SaftExportData) -> bytes:
	"""Bygg og XSD-valider en SAF-T Financial 1.40-fil."""
	_validate_input(data)
	period_entries = tuple(entry for entry in data.entries if not entry.is_opening and data.period_start <= entry.posting_date <= data.period_end)
	used_accounts = sorted({entry.account for entry in data.entries})

	root = etree.Element(
		f"{{{NS}}}AuditFile",
		nsmap={None: NS, "xsi": XSI_NS},
	)
	root.set(f"{{{XSI_NS}}}schemaLocation", f"{NS} {SCHEMA_FILENAME}")
	header = etree.SubElement(root, f"{{{NS}}}Header")
	_element(header, "AuditFileVersion", SCHEMA_VERSION)
	_element(header, "AuditFileCountry", "NO")
	_element(header, "AuditFileDateCreated", data.created_date)
	_element(header, "SoftwareCompanyName", data.software_company_name)
	_element(header, "SoftwareID", data.software_id)
	_element(header, "SoftwareVersion", data.software_version)
	company = etree.SubElement(header, f"{{{NS}}}Company")
	_add_company(company, data.company)
	_element(header, "DefaultCurrencyCode", data.company.currency)
	criteria = etree.SubElement(header, f"{{{NS}}}SelectionCriteria")
	_element(criteria, "SelectionStartDate", data.period_start)
	_element(criteria, "SelectionEndDate", data.period_end)
	_element(header, "TaxAccountingBasis", "A")

	master_files = etree.SubElement(root, f"{{{NS}}}MasterFiles")
	if used_accounts:
		accounts = etree.SubElement(master_files, f"{{{NS}}}GeneralLedgerAccounts")
		for account_name in used_accounts:
			account_data = data.accounts[account_name]
			mapping = data.account_mappings[account_name]
			account = etree.SubElement(accounts, f"{{{NS}}}Account")
			_element(account, "AccountID", mapping.account_id)
			_element(account, "AccountDescription", account_data.description)
			_element(account, "GroupingCategory", mapping.grouping_category)
			_element(account, "GroupingCode", mapping.grouping_code)
			_element(account, "AccountType", "GL")
			if account_data.created_date:
				_element(account, "AccountCreationDate", account_data.created_date)
			opening = _entry_balance(entry for entry in data.entries if entry.account == account_name and (entry.posting_date < data.period_start or entry.is_opening))
			closing = _entry_balance(entry for entry in data.entries if entry.account == account_name and entry.posting_date <= data.period_end)
			_balance(account, "Opening", opening)
			_balance(account, "Closing", closing)

	for party_type, tag in (("Customer", "Customers"), ("Supplier", "Suppliers")):
		parties = [party for party in data.parties.values() if party.party_type == party_type]
		if parties:
			party_root = etree.SubElement(master_files, f"{{{NS}}}{tag}")
			for party in sorted(parties, key=lambda item: item.party_id):
				party_element = etree.SubElement(party_root, f"{{{NS}}}{party_type}")
				_add_party(party_element, party, data.entries, data)
	if data.tax_mappings:
		tax_table = etree.SubElement(master_files, f"{{{NS}}}TaxTable")
		tax_table_entry = etree.SubElement(tax_table, f"{{{NS}}}TaxTableEntry")
		_element(tax_table_entry, "TaxType", "MVA")
		_element(tax_table_entry, "Description", "Merverdiavgift")
		for mapping in sorted(data.tax_mappings.values(), key=lambda item: item.code):
			details = etree.SubElement(tax_table_entry, f"{{{NS}}}TaxCodeDetails")
			_element(details, "TaxCode", mapping.code)
			_element(details, "TaxPercentage", mapping.percentage)
			_element(details, "Country", "NO")
			_element(details, "StandardTaxCode", mapping.standard_tax_code)
			for base_rate in sorted(set(mapping.base_rates)):
				_element(details, "BaseRate", base_rate)
	if data.analysis_catalog:
		analysis_table = etree.SubElement(master_files, f"{{{NS}}}AnalysisTypeTable")
		for (kind, identifier), (kind_description, description) in sorted(data.analysis_catalog.items()):
			entry = etree.SubElement(analysis_table, f"{{{NS}}}AnalysisTypeTableEntry")
			_element(entry, "AnalysisType", kind)
			_element(entry, "AnalysisTypeDescription", kind_description)
			_element(entry, "AnalysisID", identifier)
			_element(entry, "AnalysisIDDescription", description)
	if not period_entries:
		result = etree.tostring(root, xml_declaration=True, encoding="UTF-8", pretty_print=True)
		validate_saf_t(result)
		return result

	if period_entries:
		ledger = etree.SubElement(root, f"{{{NS}}}GeneralLedgerEntries")
		vouchers = _group_vouchers(period_entries)
		_element(ledger, "NumberOfEntries", len(vouchers))
		_element(ledger, "TotalDebit", sum((_money(entry.debit) for entry in period_entries), Decimal()))
		_element(ledger, "TotalCredit", sum((_money(entry.credit) for entry in period_entries), Decimal()))
		journal = etree.SubElement(ledger, f"{{{NS}}}Journal")
		_element(journal, "JournalID", "GL")
		_element(journal, "Description", "General Ledger")
		_element(journal, "Type", "GL")
	for (voucher_type, voucher_no, posting_date), voucher_entries in sorted(_group_vouchers(period_entries).items()):
		transaction = etree.SubElement(journal, f"{{{NS}}}Transaction")
		# Keep native issued numbers in SourceDocumentID, and distinguish dates/types.
		code = {"Sales Invoice": "SI", "Purchase Invoice": "PI", "Journal Entry": "JE", "Payment Entry": "PE"}.get(voucher_type, voucher_type)
		_element(transaction, "TransactionID", f"{code}:{voucher_no}:{posting_date.isoformat()}")
		_element(transaction, "Period", posting_date.month)
		_element(transaction, "PeriodYear", posting_date.year)
		_element(transaction, "TransactionDate", voucher_entries[0].transaction_date or posting_date)
		_element(transaction, "VoucherType", voucher_type)
		_element(transaction, "VoucherDescription", voucher_type)
		_element(transaction, "Description", voucher_entries[0].remarks or voucher_no)
		_element(transaction, "SystemEntryDate", voucher_entries[0].system_entry_date or posting_date)
		_element(transaction, "GLPostingDate", posting_date)
		if voucher_entries[0].modified_date:
			_element(transaction, "ModificationDate", voucher_entries[0].modified_date)
		for entry in voucher_entries:
			line = etree.SubElement(transaction, f"{{{NS}}}Line")
			_element(line, "RecordID", entry.record_id)
			_element(line, "AccountID", data.account_mappings[entry.account].account_id)
			for kind, identifier in entry.analyses:
				analysis = etree.SubElement(line, f"{{{NS}}}Analysis")
				_element(analysis, "AnalysisType", kind)
				_element(analysis, "AnalysisID", identifier)
				amount = etree.SubElement(analysis, f"{{{NS}}}{'DebitAnalysisAmount' if entry.debit else 'CreditAnalysisAmount'}")
				_element(amount, "Amount", entry.debit if entry.debit else entry.credit)
			_element(line, "SourceDocumentID", voucher_no)
			if entry.party_type == "Customer":
				_element(line, "CustomerID", entry.party or "")
			elif entry.party_type == "Supplier":
				_element(line, "SupplierID", entry.party or "")
			_element(line, "Description", entry.remarks or voucher_no)
			amount = etree.SubElement(line, f"{{{NS}}}{'DebitAmount' if _money(entry.debit) else 'CreditAmount'}")
			_element(amount, "Amount", _money(entry.debit) if _money(entry.debit) else _money(entry.credit))
			if entry.currency_code and entry.currency_amount is not None:
				_element(amount, "CurrencyCode", entry.currency_code)
				ET_amount = etree.SubElement(amount, f"{{{NS}}}CurrencyAmount")
				ET_amount.text = format(entry.currency_amount, "f")
			information = entry.tax_information or ((TaxInformation(entry.tax_code, entry.tax_base),) if entry.tax_code else ())
			for tax_information in information:
				_add_tax_information(line, entry, tax_information, data.tax_mappings[tax_information.code])
			if entry.reference_number:
				_element(line, "ReferenceNumber", entry.reference_number)
			if entry.due_date:
				_element(line, "DueDate", entry.due_date)

	result = etree.tostring(root, xml_declaration=True, encoding="UTF-8", pretty_print=True)
	validate_saf_t(result)
	return result


def validate_saf_t(xml: bytes | str) -> None:
	"""Valider en fil mot den medleverte, offisielle XSD 1.40."""
	schema = etree.XMLSchema(etree.parse(str(SCHEMA_PATH)))
	document = etree.fromstring(xml.encode() if isinstance(xml, str) else xml)
	if not schema.validate(document):
		errors = "; ".join(str(error) for error in schema.error_log)
		raise SaftExportError(f"SAF-T-filen består ikke XSD-validering: {errors}")
