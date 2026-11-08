"""Map existing quarterly report sources; never allocate or calculate VAT."""
from decimal import Decimal

import frappe
from frappe.utils import getdate

from erpnext_norway import saft_builder as xml
from erpnext_norway import vat_quarterly as quarterly
from erpnext_norway.saft import unsupported
from erpnext_norway.vat import is_vat_account


def source_rows(doc, cache):
    from erpnext_norway.erpnext_norway.report.norsk_mva_spesifikasjon.norsk_mva_spesifikasjon import collect
    date = getdate(doc.get('bill_date') or doc.posting_date)
    if doc.doctype == 'Journal Entry':
        from erpnext_norway.vat_import import journal_date
        date = journal_date(doc)
    start, end = quarterly.period(date)
    key = doc.company, start, end
    if key not in cache:
        cache[key] = collect({'company': doc.company, 'from_date': start, 'to_date': end})
    return [r for r in cache[key] if (r['voucher_type'], r['voucher']) == (doc.doctype, doc.name)]


def invoice_taxes(doc, rows, info, mappings, cache):
    if not any(item.get(quarterly.ITEM) for item in doc.items):
        return
    for source in source_rows(doc, cache):
        if not source.get('quarterly_source') or source['vat_code'] == '0':
            continue
        code = source['vat_code']
        item = next((r for r in doc.items if r.idx == source['line']), None)
        candidates = [r for r in rows if item and r.account == item.expense_account and r.name in info]
        exact = [r for r in candidates if r.voucher_detail_no == item.name]
        candidates = exact or candidates
        if (code not in {'87', '89'} or not candidates
                or any(source[key] for key in ('output_vat', 'input_vat', 'net_vat'))):
            unsupported(doc, 'Kvartalsgrunnlaget mangler entydig kobling til kildefakturaen.')
        # The supplier's code0 remains. The report supplies the separate fiscal
        # classification/base; its VAT is not stored per invoice GL line.
        for row in candidates:
            info[row.name].append(xml.TaxInformation(code,
                abs(xml._money(source['base_amount'])), Decimal(0)))
        mappings[code] = xml.TaxMapping(code, Decimal(str(source['vat_rate'])), code, (Decimal(0),))


def journal_taxes(doc, rows, cache):
    report = source_rows(doc, cache)
    # A generated quarter journal posts VAT cost and liability, not the service
    # base. Keep its actual ledger entries without a second TaxInformation.
    expected = {}
    for row in report:
        for account, amount in row['vat_accounts'].items():
            expected[account] = expected.get(account, Decimal()) + xml._money(amount)
    actual = {}
    for row in rows:
        if is_vat_account(row.account):
            actual[row.account] = actual.get(row.account, Decimal()) + xml._money(row.credit) - xml._money(row.debit)
    if not report or actual != expected or any(r['base_amount'] for r in report):
        unsupported(doc, 'Kvartalsbilaget stemmer ikke med eksisterende MVA-spesifikasjon.')
    for account in actual:
        for side in ('debit', 'credit'):
            if sum((xml._money(r.get(side)) for r in rows if r.account == account), Decimal()) != sum(
                    (xml._money(r.get(side)) for r in doc.accounts if r.account == account), Decimal()):
                unsupported(doc, 'Kvartalsbilagets brutto MVA stemmer ikke med hovedboken.')
    return {}, {}
