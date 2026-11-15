"""ENK classification and documented annual facts over native report results.

Amounts come from the native P&L/Trial Balance; no postings or stored totals.
Unassessed values remain empty, including on standard CSV/XLSX export.
"""
from collections import defaultdict
from dataclasses import asdict
from decimal import Decimal

import frappe

from erpnext_norway import enk_catalog
from erpnext_norway.enk_person_income import PersonalIncomeInput, calculate_personal_income, YearEndError

ZERO = Decimal(0)
ROLES = {'Capital income': 'capital_income', 'Financial gains': 'financial_gains',
    'Capital costs': 'capital_costs', 'Financial losses': 'financial_losses',
    'Private debt interest': 'private_debt_interest', 'Special deductions': 'special_deductions',
    'Qualifying business debt interest': 'qualifying_business_debt_interest'}
AUTO_CORRECTIONS = {
    ('7799', 'Annen kostnad, ikke fradragsberettiget'),
    ('7835', 'Tap på fordringer, ikke fradragsberettiget'),
    ('7825', 'Innkommet på tidligere nedskrevne fordringer, ikke skattepliktig'),
}


def checked_account(name, company):
    account = frappe.get_doc('Account', name)
    account.check_permission('read')
    if account.company != company or account.is_group:
        frappe.throw('Årsopplysninger krever en bokføringskonto i samme foretak.')
    return account


def validate_facts(doc):
    from erpnext_norway.enk_tax import number
    seen = set()
    for row in doc.get('tax_values') or []:
        account = checked_account(row.account, doc.company)
        if account.root_type not in {'Asset', 'Liability', 'Equity'} or row.account in seen:
            frappe.throw('Oppgi hver balansekonto bare én gang i skatte- og formuesverdiene.')
        seen.add(row.account)
        if row.get('outside_saldo') and (account.root_type != 'Asset' or account.account_type == 'Accumulated Depreciation' or row.tax_method == 'Not assessed'):
            frappe.throw('Driftsmiddel utenfor saldogruppene krever en eiendelskonto med vurdert skatteverdi og dokumentert behandling.')
        if number(row.get('non_saldo_deduction')) < 0 or (not row.get('outside_saldo') and number(row.get('non_saldo_deduction'))):
            frappe.throw('Fradrag utenfor saldo krever uttrykkelig valg og positivt eller null dokumentert årsfradrag.')
        if row.get('result_effect') and (row.tax_method == 'Not assessed' or row.get('outside_saldo') or account.root_type == 'Equity' or account.account_type in {'Fixed Asset', 'Accumulated Depreciation'}):
            frappe.throw('Resultatvirkning av verdiforskjell krever vurdert skatteverdi på annen eiendel/gjeld; skattesaldo og avskrivninger behandles separat.')
        if not (row.reference or '').strip():
            frappe.throw('Dokumenter valg av skatte- og formuesverdi.')
        for field in ('tax_opening', 'tax_closing', 'wealth_value'):
            number(row.get(field))
        if row.tax_method != 'Documented values' and (number(row.tax_opening) or number(row.tax_closing)):
            frappe.throw('Manuelle skatteverdier krever valget Dokumenterte verdier.')
        if row.wealth_method != 'Documented value' and number(row.wealth_value):
            frappe.throw('Manuell formuesverdi krever valget Dokumentert verdi.')
    seen = set()
    for row in doc.get('person_items') or []:
        if row.role not in ROLES or not (row.reference or '').strip():
            frappe.throw('Personinntektsposter krever gyldig behandling og dokumentasjon.')
        number(row.amount)
        if row.account:
            account = checked_account(row.account, doc.company)
            roots = {'Income'} if row.role in {'Capital income', 'Financial gains'} else {'Expense'}
            if account.root_type not in roots or row.account in seen or number(row.amount):
                frappe.throw('Velg hver resultatkonto én gang med riktig personinntektsbehandling og tomt beløpsfelt.')
            seen.add(row.account)
        elif number(row.amount) < 0:
            frappe.throw('Dokumenterte personinntektsbeløp må være positive eller null.')
    if doc.get('shielding_choice') != 'Documented amount' and number(doc.get('shielding_amount')):
        frappe.throw('Skjermingsbeløp krever valget Dokumentert beløp.')
    if not number(doc.get('qualifying_business_debt')) and any(
            r.role == 'Qualifying business debt interest' and (r.account or number(r.amount))
            for r in doc.get('person_items') or []):
        frappe.throw('Renter på kvalifiserende foretaksgjeld krever dokumentert gjeldsgrunnlag.')


def complete_basis(doc, basis, accounts, pnl_amounts, trial_amounts, rows, start, end):
    from erpnext_norway.enk_tax import number, money, native_report, accounts_for_pool
    # Native closing entries must be included in equity/balance figures, while
    # the year's P&L above deliberately excludes them. No invented closing JE.
    closing = native_report('Trial Balance', doc, start, end, include_closing=True)
    balances = {r['account']: r for r in closing['result'] if r and r.get('account') in accounts}
    mappings = enk_catalog.resolve(accounts, start.year)
    documented = {r.account: r for r in doc.get('tax_values') or []}
    other_deduction = sum((number(r.get('non_saldo_deduction')) for r in documented.values() if r.get('outside_saldo')), ZERO)
    basis['non_saldo_deduction'] = money(other_deduction)
    basis['tax_profit'] -= other_deduction
    explicit = {r['account'] for r in basis['corrections'] if r['account']}
    for account in accounts.values():
        if (account.account_number, account.account_name) in AUTO_CORRECTIONS and account.name not in explicit:
            amount = pnl_amounts.get(account.name, ZERO)
            if amount:
                basis['corrections'].append(dict(account=account.name, amount=amount,
                    reason='Tilbakeføring etter kontoens uttrykkelige skattebehandling',
                    reference=account.name))
                basis['tax_profit'] += amount
    adjustments = defaultdict(lambda: ZERO)
    for row in basis['corrections']:
        if row['account']:
            adjustments[row['account']] += row['amount']
    annual = []
    issues = []
    posts = defaultdict(lambda: dict(book=ZERO, opening=ZERO, closing=ZERO, tax_opening=ZERO, tax_closing=ZERO,
        tax_assessed=True, accounts=[]))
    for name, account in sorted(accounts.items(), key=lambda pair: (pair[1].account_number or '', pair[0])):
        native = balances.get(name, {})
        opening = money(native.get('opening_debit')) - money(native.get('opening_credit'))
        closing_value = money(native.get('closing_debit')) - money(native.get('closing_credit'))
        debit, credit = money(native.get('debit')), money(native.get('credit'))
        profit_value = pnl_amounts.get(name, ZERO)
        value = documented.get(name)
        if not any((opening, closing_value, debit, credit, profit_value)) and not value:
            continue
        mapping = mappings[name]
        tax_opening = tax_closing = wealth = None
        if value and value.tax_method == 'Book values confirmed':
            tax_opening, tax_closing = opening, closing_value
        elif value and value.tax_method == 'Documented values':
            tax_opening, tax_closing = money(value.tax_opening), money(value.tax_closing)
        if value:
            if value.wealth_method == 'Tax value before discount':
                wealth = tax_closing
            elif value.wealth_method == 'Documented value':
                wealth = money(value.wealth_value)
            elif value.wealth_method == 'Not taxable':
                wealth = ZERO
        if value and value.get('result_effect'):
            if any(value.account == p.asset_account or value.account in accounts_for_pool(p, doc.company) for p in doc.pools):
                frappe.throw('Verdiforskjell på skattesaldo kan ikke også resultatkorrigeres som annen balansepost.')
            amount = money((tax_closing - closing_value) - (tax_opening - opening))
            basis['corrections'].append(dict(account=name, amount=amount,
                reason='Endring i dokumentert skatte-/bokført verdiforskjell', reference=value.reference))
            basis['tax_profit'] += amount
        balance_account = account.root_type in {'Asset', 'Liability', 'Equity'}
        if not mapping:
            issues.append('Næringspost må vurderes: ' + name)
        if balance_account and (opening or closing_value) and tax_closing is None:
            issues.append('Skatteverdi må vurderes: ' + name)
        if account.root_type in {'Asset', 'Liability'} and closing_value and wealth is None:
            issues.append('Formuesverdi før rabatt må vurderes: ' + name)
        # Debit-minus-credit is retained in account detail, including reversals.
        annual.append(dict(account=name, root_type=account.root_type, opening=opening, debit=debit, credit=credit,
            closing=closing_value, book=profit_value if not balance_account else closing_value,
            tax_opening=tax_opening, tax_closing=tax_closing, wealth=wealth,
            category=mapping['category'] if mapping else '', code=mapping['code'] if mapping else '',
            label=mapping['label'] if mapping else 'Ikke koblet', reference=value.reference if value else ''))
        if mapping:
            key = (mapping['category'], mapping['code'], mapping['label'])
            post = posts[key]
            # Income/expense totals are native P&L signs. Balance presentation
            # uses each official post's polarity, never abs() on reversals.
            sign = -1 if account.root_type in {'Liability', 'Equity'} else 1
            if mapping['polarity'] == 'negativ':
                sign *= -1
            post['book'] += (closing_value * sign if balance_account else profit_value * sign)
            post['opening'] += opening * sign
            post['closing'] += closing_value * sign
            post['accounts'].append(name)
            if not balance_account:
                post['tax_assessed'] = False
            if balance_account:
                if tax_opening is None or tax_closing is None:
                    post['tax_assessed'] = False
                else:
                    post['tax_opening'] += tax_opening * sign
                    post['tax_closing'] += tax_closing * sign
    # The existing 2068 owner account and actual expense credit express private
    # ELK usage. Split gross 6995 / negative post 6998 for the portal without
    # adding the amount to taxable profit a second time.
    elk = {a.name for a in accounts.values() if (a.account_number, a.account_name) ==
        ('2068', 'Private kostnader til elektronisk kommunikasjon') and a.root_type == 'Equity'}
    for voucher in {(r.voucher_type, r.voucher_no) for r in rows if r.account in elk}:
        lines = [r for r in rows if (r.voucher_type, r.voucher_no) == voucher]
        private = sum((number(r.debit)-number(r.credit) for r in lines if r.account in elk), ZERO)
        expense_lines = [r for r in lines if mappings.get(r.account) and mappings[r.account]['code']=='6995']
        credits = sum((number(r.credit)-number(r.debit) for r in expense_lines), ZERO)
        if not private or private != credits:
            continue
        catalog = enk_catalog.fields(start.year)
        for code in ('6995', '6998'):
            label = catalog[('annenDriftskostnad', code)]['label']
            post = posts[('annenDriftskostnad', code, label)]
            post['book'] += private
            post['accounts'].extend(sorted(elk))
    basis['annual_accounts'] = annual
    basis['annual_posts'] = [dict(category=k[0], code=k[1], label=k[2], **v) for k, v in sorted(posts.items())]
    basis['gain_loss'] = asdict(basis['gain_loss'])
    basis['person_items'] = []
    basis['person_income'] = None
    basis['person_reference'] = doc.get('person_reference') or ''
    basis['shielding_base_net'] = money(doc.get('shielding_base_net'))
    basis['capital_return_base_gross'] = money(doc.get('capital_return_base_gross'))
    basis['qualifying_business_debt'] = money(doc.get('qualifying_business_debt'))
    if doc.get('person_enabled'):
        amounts = defaultdict(lambda: ZERO)
        for row in doc.person_items:
            amount = (pnl_amounts.get(row.account, ZERO) - adjustments[row.account] if row.account
                and accounts[row.account].root_type == 'Expense' else
                pnl_amounts.get(row.account, ZERO) if row.account else number(row.amount))
            # A net reversal belongs on the opposite side of the bridge.
            role = ROLES[row.role]
            if amount < 0:
                opposites = {'capital_income': 'capital_costs', 'financial_gains': 'financial_losses',
                    'capital_costs': 'capital_income', 'financial_losses': 'financial_gains'}
                if role not in opposites:
                    frappe.throw('Netto reverserte rente-/fradragsposter krever dokumentert årsbeløp etter skattebehandling.')
                role, amount = opposites[role], -amount
            amounts[role] += amount
            basis['person_items'].append(dict(role=row.role, account=row.account, amount=money(amount), reference=row.reference))
        choice = doc.get('shielding_choice')
        if choice == 'Not assessed' and number(doc.get('shielding_base_net')):
            issues.append('Skjermingsfradrag er ikke vurdert; personinntekten beregnes ikke med et antatt nullfradrag.')
        else:
            shielding = number(doc.get('shielding_amount')) if choice == 'Documented amount' else ZERO
            try:
                result = calculate_personal_income(basis['tax_profit'], PersonalIncomeInput(
                    capital_return_base=number(doc.get('capital_return_base_gross')),
                    qualifying_business_debt=number(doc.get('qualifying_business_debt')),
                    documented_shielding=shielding, carried_forward_negative=number(doc.get('person_negative_carry')),
                    **amounts))
            except YearEndError as error:
                frappe.throw(str(error))
            basis['person_income'] = asdict(result)
    else:
        issues.append('Personinntektsgrunnlag er ikke vurdert i årets skatteopplysninger.')
    basis['owner_movements'] = [dict(account=r.account, amount=money(number(r.debit)-number(r.credit)),
        doctype=r.voucher_type, name=r.voucher_no, posting_date=r.posting_date)
        for r in rows if r.account in accounts and accounts[r.account].root_type == 'Equity']
    basis['issues'] = issues
    return basis
