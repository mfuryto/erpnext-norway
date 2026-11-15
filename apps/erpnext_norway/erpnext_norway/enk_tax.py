"""Norwegian tax facts reconciled to native reports and dated source GL.

No posting, duplicated ledger, saved calculation snapshot or core override.
"""
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

import frappe
from frappe.utils import getdate
from frappe.desk.query_report import run as run_report
from erpnext_norway.enk_tax_rules import SaldoGroup, calculate_saldo_pool, RuleValidationError

FACTS = 'Norwegian Tax Facts'
ZERO = Decimal(0)


def number(value):
    try:
        value = Decimal(str(value or 0))
        if not value.is_finite():
            raise InvalidOperation
        return value
    except (InvalidOperation, ValueError):
        frappe.throw('Skatteopplysninger må inneholde endelige tall.')


def money(value):
    return number(value).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def company_year(doc):
    company = frappe.get_doc('Company', doc.company)
    company.check_permission('read')
    fy = frappe.get_doc('Fiscal Year', doc.fiscal_year)
    fy.check_permission('read')
    if (company.country != 'Norway' or company.default_currency != 'NOK'
            or getdate(fy.year_start_date) != date(2026, 1, 1)
            or getdate(fy.year_end_date) != date(2026, 12, 31)):
        frappe.throw('Næringsgrunnlaget er kvalifisert for norsk ENK uten ansatte, NOK og kalenderåret 2026.')
    return company, getdate(fy.year_start_date), getdate(fy.year_end_date)


def accounts_for_pool(row, company):
    account = frappe.get_doc('Account', row.asset_account)
    account.check_permission('read')
    if account.company != company or account.root_type != 'Asset':
        frappe.throw('Saldogruppen må bruke en eiendelskonto i samme foretak.')
    accounts = frappe.get_list('Account', filters={'company': company, 'is_group': 0,
        'lft': ['>=', account.lft], 'rgt': ['<=', account.rgt]},
        fields=['name', 'account_type'], limit_page_length=0)
    if not accounts or any(a.account_type != 'Fixed Asset' for a in accounts):
        frappe.throw('Velg en konto eller kontogruppe som bare inneholder anleggsmiddelkontoer (typen Anleggsmiddel).')
    return {a.name for a in accounts}


def validate(doc):
    company_year(doc)
    old = doc.get_doc_before_save()
    if old and (old.company != doc.company or old.fiscal_year != doc.fiscal_year):
        frappe.throw('Foretak og inntektsår kan ikke endres på lagrede skatteopplysninger.')
    groups, accounts, adjustments = set(), set(), set()
    for row in doc.pools:
        if row.saldo_group not in {'a', 'd'} or row.saldo_group in groups:
            frappe.throw('Bruk én samlesaldo for hver av saldogruppene a og d.')
        groups.add(row.saldo_group)
        selected = accounts_for_pool(row, doc.company)
        if selected & accounts:
            frappe.throw('En anleggsmiddelkonto kan ikke inngå i flere saldogrupper.')
        accounts |= selected
        if not (row.opening_reference or '').strip():
            frappe.throw('Dokumenter inngående skattesaldo, også når saldoen er null.')
        number(row.opening_balance)
        for field in ('depreciation', 'direct_income', 'additional_income'):
            if number(row.get(field)) < 0:
                frappe.throw('Valgt avskrivning og inntektsføring kan ikke være negativ.')
    for row in doc.adjustments:
        if not (row.reason or '').strip() or not (row.reference or '').strip():
            frappe.throw('Skattekorreksjoner krever begrunnelse og dokumentasjon.')
        number(row.amount)
        if row.account:
            account = frappe.get_doc('Account', row.account)
            account.check_permission('read')
            if (account.company != doc.company or account.root_type != 'Expense' or account.is_group
                    or account.account_type == 'Depreciation' or row.account in adjustments):
                frappe.throw('Velg hver kostnadskonto én gang; avskrivningskontoer behandles separat.')
            if not ZERO <= number(row.disallowed_percent) <= 100 or number(row.amount):
                frappe.throw('Kontokorreksjon krever prosent mellom 0 og 100 og tomt beløpsfelt.')
            adjustments.add(row.account)
        elif number(row.disallowed_percent) not in (ZERO, Decimal(100)):
            frappe.throw('Prosent brukes bare når en kostnadskonto er valgt.')


def native_report(name, doc, start, end):
    filters = {'company': doc.company, 'fiscal_year': doc.fiscal_year,
        'filter_based_on': 'Date Range', 'period_start_date': str(start), 'period_end_date': str(end),
        'from_date': str(start), 'to_date': str(end), 'periodicity': 'Yearly',
        'accumulated_values': 1, 'include_default_book_entries': 1, 'show_zero_values': 1,
        'show_net_values': 1, 'with_period_closing_entry_for_opening': 1,
        'with_period_closing_entry_for_current_period': 0}
    return run_report(name, filters=frappe.as_json(filters), ignore_prepared_report=True,
        js_filters=[{'fieldname': 'company', 'fieldtype': 'Link', 'options': 'Company'}])


def check_direct_asset_cost(source, rows, accounts):
    """Reconcile native saved valuation with actual direct PI asset GL.

    Detect the demonstrated periodic-inventory valuation mismatch in old data;
    do not repair accounting or substitute today's Asset Category defaults.
    """
    if source.doctype != 'Purchase Invoice' or any(item.purchase_receipt for item in source.items):
        return
    items = [item for item in source.items if item.is_fixed_asset]
    if not items or not source.update_stock:
        return
    expected = sum((number(item.valuation_rate) * number(item.stock_qty) for item in items), ZERO)
    actual = sum((number(r.debit) - number(r.credit) for r in rows
        if r.voucher_type == source.doctype and r.voucher_no == source.name and r.account in accounts
        and accounts[r.account].account_type == 'Fixed Asset'), ZERO)
    if money(expected) != money(actual):
        frappe.throw('Avstem driftsmiddelverdsetting mot hovedboken på {0}. Korriger oppsett og kilde gjennom vanlig rettingsflyt.'.format(
            frappe.utils.escape_html(source.name)))


def disposal(source, rows, selected, accounts):
    """Use actual native sale GL, not today's Asset Category/default accounts.

    The pinned core merges away voucher_detail_no on ordinary asset sales.
    A single tax pool needs no invented per-asset book-value allocation.
    """
    gl = [r for r in rows if r.voucher_type == 'Sales Invoice' and r.voucher_no == source.name]
    items = [item for item in source.items if item.is_fixed_asset and item.asset]
    asset_rows = [r for r in gl if r.account in accounts and accounts[r.account].account_type == 'Fixed Asset']
    group_by_account = {name: group for group, names in selected.items() for name in names}
    if (source.docstatus != 1 or not items or not asset_rows
            or any(r.account not in group_by_account for r in asset_rows)):
        frappe.throw('Driftsmiddelsalget mangler kvalifisert skattesaldo.')
    company_book = frappe.get_cached_value('Company', source.company, 'default_finance_book')
    if any(item.finance_book not in {None, '', company_book} for item in items):
        frappe.throw('Driftsmiddelsalg i andre regnskapsbøker er ikke kvalifisert i næringsgrunnlaget.')
    groups = {group_by_account[r.account] for r in asset_rows}
    proceeds = {}
    for item in items:
        if len(groups) == 1:
            group = next(iter(groups))
        else:
            bound = {group_by_account[r.account] for r in asset_rows
                if r.voucher_detail_no in {item.name, item.asset}}
            if len(bound) != 1:
                frappe.throw('Salg fra flere skattesaldoer på samme faktura mangler entydige native kildelinjer.')
            group = next(iter(bound))
        proceeds[group] = proceeds.get(group, ZERO) + number(item.base_net_amount)
    gain_accounts = {item.income_account for item in items}
    ordinary_accounts = {item.income_account for item in source.items if item not in items}
    ordinary_accounts |= {r.account_head for r in source.taxes if number(r.base_tax_amount)}
    ordinary_accounts |= {source.get(key) for key, amount in (('write_off_account', 'write_off_amount'),
        ('additional_discount_account', 'discount_amount'), ('loyalty_redemption_account', 'loyalty_amount'))
        if source.get(key) and number(source.get(amount))}
    if gain_accounts & ordinary_accounts or any(name not in accounts
            or accounts[name].root_type not in {'Income', 'Expense'} for name in gain_accounts):
        frappe.throw('Gevinst/tap ved driftsmiddelsalg må kunne skilles fra andre fakturalinjer og gebyrer i hovedboken.')
    book_result = sum((number(r.credit) - number(r.debit) for r in gl if r.account in gain_accounts), ZERO)
    return dict(proceeds=proceeds, book_result=book_result, accounts=gain_accounts)


def collect(company, fiscal_year):
    names = frappe.get_list(FACTS, filters={'company': company, 'fiscal_year': fiscal_year},
        pluck='name', limit_page_length=2)
    if len(names) != 1:
        frappe.throw('Opprett skatteopplysninger for foretaket og inntektsåret først.')
    doc = frappe.get_doc(FACTS, names[0])
    doc.check_permission('read')
    validate(doc)
    company, start, end = company_year(doc)
    for dt in ('Account', 'GL Entry'):
        frappe.has_permission(dt, 'read', throw=True)
    pnl = native_report('Profit and Loss Statement', doc, start, end)
    trial = native_report('Trial Balance', doc, start, end)
    accounts = {a.name: a for a in frappe.get_list('Account', filters={'company': company.name,
        'is_group': 0}, fields=['name', 'root_type', 'account_type'], limit_page_length=0)}
    if len(accounts) != frappe.db.count('Account', {'company': company.name, 'is_group': 0}):
        frappe.throw('Næringsgrunnlaget krever tilgang til hele kontoplanen for foretaket.', frappe.PermissionError)
    pnl_amounts = {r['account']: money(r.get('total')) for r in pnl['result']
        if r and r.get('account') in accounts}
    trial_amounts = {r['account']: r for r in trial['result'] if r and r.get('account') in accounts}
    summary = pnl['report_summary']
    if len(summary) != 3:
        frappe.throw('Kjernens resultatrapport ga ikke et entydig årsresultat.')
    book_profit = money(summary[2]['value'])
    book_depreciation = sum((pnl_amounts.get(a.name, ZERO) for a in accounts.values()
        if a.account_type == 'Depreciation'), ZERO)
    rows = frappe.get_list('GL Entry', filters={'company': company.name,
        'posting_date': ['between', [start, end]], 'is_cancelled': 0},
        fields=['name', 'account', 'posting_date', 'voucher_type', 'voucher_no', 'voucher_detail_no',
            'debit', 'credit', 'finance_book', 'is_opening'], limit_page_length=0)
    if len(rows) != frappe.db.count('GL Entry', {'company': company.name,
            'posting_date': ['between', [start, end]], 'is_cancelled': 0}):
        frappe.throw('Næringsgrunnlaget krever tilgang til hele årets hovedbok for foretaket.', frappe.PermissionError)
    rows = [r for r in rows if r.finance_book in {None, '', company.default_finance_book}
        and r.voucher_type != 'Period Closing Voucher' and r.is_opening != 'Yes']
    selected = {r.saldo_group: accounts_for_pool(r, company.name) for r in doc.pools}
    assigned = set().union(*selected.values()) if selected else set()
    used_fixed = {r.account for r in rows if r.account in accounts
        and accounts[r.account].account_type == 'Fixed Asset'}
    used_fixed |= {a.name for a in accounts.values() if a.account_type == 'Fixed Asset'
        and any(money(trial_amounts.get(a.name, {}).get(k)) for k in ('opening_debit', 'opening_credit'))}
    if used_fixed - assigned or (book_depreciation and not selected):
        frappe.throw('Anleggsmidler eller avskrivninger mangler kvalifisert skattesaldo. Bare gruppe a og d er dekket.')
    sources, pools, disposals = {}, [], {}
    book_disposal = ZERO
    for row in rows:
        if row.account in assigned and row.voucher_type == 'Sales Invoice' and row.voucher_no not in disposals:
            source = frappe.get_doc('Sales Invoice', row.voucher_no)
            source.check_permission('read')
            disposals[source.name] = disposal(source, rows, selected, accounts)
    for pool in doc.pools:
        adds, proceeds = ZERO, ZERO
        for row in rows:
            if row.account not in selected[pool.saldo_group]:
                continue
            key = (row.voucher_type, row.voucher_no)
            if key not in sources:
                source = frappe.get_doc(*key)
                source.check_permission('read')
                if source.docstatus != 1 or source.get('company') != company.name:
                    frappe.throw('Skattesaldoens kilde må være bokført i samme foretak.')
                sources[key] = source
            source = sources[key]
            if row.voucher_type in {'Purchase Invoice', 'Purchase Receipt', 'Landed Cost Voucher'}:
                check_direct_asset_cost(source, rows, accounts)
                adds += number(row.debit) - number(row.credit)
            elif row.voucher_type != 'Sales Invoice':
                frappe.throw('Skattesaldoen har en kilde som ikke er kvalifisert: {0} {1}.'.format(*key))
        for name in selected[pool.saldo_group]:
            expected = money(trial_amounts.get(name, {}).get('debit')) - money(trial_amounts.get(name, {}).get('credit'))
            actual = sum((money(r.debit) - money(r.credit) for r in rows if r.account == name), ZERO)
            if money(expected) != money(actual):
                frappe.throw('Kildene til skattesaldoen stemmer ikke med kjernens saldobalanse.')
        proceeds = sum((d['proceeds'].get(pool.saldo_group, ZERO) for d in disposals.values()), ZERO)
        try:
            result = calculate_saldo_pool(group=SaldoGroup(pool.saldo_group), year_end=end,
                opening_balance=number(pool.opening_balance), acquisitions=adds, disposal_proceeds=proceeds,
                disposal_proceeds_taken_to_income=number(pool.direct_income),
                requested_depreciation=None if pool.use_maximum else number(pool.depreciation),
                write_off_small_positive_balance=bool(pool.write_off_small_balance),
                additional_negative_balance_income=number(pool.additional_income))
        except RuleValidationError as error:
            frappe.throw(str(error))
        pools.append(result)
    book_disposal = sum((d['book_result'] for d in disposals.values()), ZERO)
    disposal_accounts = set().union(*(d['accounts'] for d in disposals.values())) if disposals else set()
    # A native disposal account can itself be classified as Depreciation.
    # Remove that result from the depreciation add-back to avoid counting it twice.
    book_depreciation += sum((number(r.credit) - number(r.debit) for r in rows
        if r.voucher_type == 'Sales Invoice' and r.voucher_no in disposals
        and r.account in disposals[r.voucher_no]['accounts'] and r.account in accounts
        and accounts[r.account].account_type == 'Depreciation'), ZERO)
    corrections = []
    for row in doc.adjustments:
        if row.account and row.account in disposal_accounts:
            frappe.throw('En kostnadskonto med driftsmiddelgevinst/tap kan ikke også få prosentkorreksjon.')
        amount = (pnl_amounts.get(row.account, ZERO) * number(row.disallowed_percent) / 100
            if row.account else number(row.amount))
        corrections.append({'account': row.account, 'amount': money(amount), 'reason': row.reason,
            'reference': row.reference})
    tax_depreciation = sum((r.depreciation_deduction for r in pools), ZERO)
    tax_income = sum((r.negative_balance_income + r.disposal_proceeds_taken_to_income for r in pools), ZERO)
    tax_profit = book_profit + book_depreciation - tax_depreciation - book_disposal + tax_income
    tax_profit += sum((r['amount'] for r in corrections), ZERO)
    book_assets = sum((money(trial_amounts.get(a.name, {}).get('closing_debit'))
        - money(trial_amounts.get(a.name, {}).get('closing_credit')) for a in accounts.values()
        if a.account_type in {'Fixed Asset', 'Accumulated Depreciation'}), ZERO)
    return dict(document=doc.name, book_income=money(summary[0]['value']), book_expenses=money(summary[1]['value']),
        book_profit=book_profit, book_depreciation=money(book_depreciation), book_disposal=money(book_disposal),
        tax_depreciation=money(tax_depreciation), tax_income=money(tax_income), tax_profit=money(tax_profit),
        book_assets=book_assets, pools=pools, corrections=corrections,
        sources=[dict(doctype=dt, name=name) for dt, name in sorted(sources)])
