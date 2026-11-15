"""Tax reconciliation, using native Profit and Loss and Trial Balance reports."""
import frappe
from erpnext_norway.enk_tax import collect


def execute(filters=None):
    filters = frappe._dict(filters or {})
    if not filters.company or not filters.fiscal_year:
        frappe.throw('Velg foretak og regnskapsår.')
    basis = collect(filters.company, filters.fiscal_year)
    rows = []

    def add(section, label, amount=None, account=None):
        rows.append(dict(section=section, description=label,
            amount=float(amount) if amount is not None else None, account=account))

    for field, label in [('book_income', 'Bokførte inntekter'), ('book_expenses', 'Bokførte kostnader'),
            ('book_profit', 'Bokført årsresultat'), ('book_depreciation', 'Tilbakeføring av bokførte avskrivninger'),
            ('tax_depreciation', 'Fradrag for skattemessige avskrivninger'),
            ('book_disposal', 'Tilbakeføring av bokført gevinst/tap ved driftsmiddelsalg'),
            ('tax_income', 'Skattepliktig inntekt fra saldo og direkte inntektsført salgsvederlag')]:
        sign = -1 if field in {'tax_depreciation', 'book_disposal'} else 1
        add('Resultatavstemming', label, sign * basis[field])
    for row in basis['corrections']:
        add('Skattekorreksjoner', row['reason'] + ' — ' + row['reference'], row['amount'], row['account'])
    add('Resultatavstemming', 'Beregnet næringsresultat innenfor avgrenset omfang', basis['tax_profit'])
    tax_closing = sum(p.closing_balance for p in basis['pools'])
    add('Verdiavstemming', 'Bokført nettoverdi anleggsmidler', basis['book_assets'])
    add('Verdiavstemming', 'Utgående skattesaldo (negativ saldo vises med minus)', tax_closing)
    add('Verdiavstemming', 'Bokført nettoverdi minus skattesaldo', basis['book_assets'] - tax_closing)
    for pool in basis['pools']:
        section = 'Saldogruppe ' + pool.group.value
        for field, label in [('opening_balance', 'Inngående skattesaldo'), ('acquisitions', 'Årets netto tilgang'),
                ('disposal_proceeds', 'Årets salgsvederlag'), ('disposal_proceeds_taken_to_income', 'Direkte inntektsført vederlag'),
                ('balance_before_year_end_adjustments', 'Saldo før årets avskrivning/inntektsføring'),
                ('depreciation_deduction', 'Skattemessig avskrivning'), ('negative_balance_income', 'Inntektsført negativ saldo'),
                ('closing_balance', 'Utgående skattesaldo')]:
            add(section, label, getattr(pool, field))
    columns = [dict(fieldname='section', label='Del', fieldtype='Data', width=180),
        dict(fieldname='description', label='Forklaring', fieldtype='Data', width=490),
        dict(fieldname='amount', label='Beløp (NOK)', fieldtype='Currency', options='NOK', width=160),
        dict(fieldname='account', label='Konto', fieldtype='Link', options='Account', width=210)]
    message = ('Grunnlag for norsk ENK uten ansatte, NOK og 2026; skattesaldo a/d. '
        'Skatteopplysninger: ' + frappe.utils.escape_html(basis['document']) + '. '
        'Dette er ikke en full næringsspesifikasjon, personinntektsberegning eller skatteinnsending. '
        'Øvrige forskjeller må dokumenteres i skatteopplysningene. '
        'Kontroller personlige opplysninger, formuesverdier og innleveringskrav separat.')
    summary = [dict(value=float(basis['book_profit']), label='Bokført årsresultat', datatype='Currency', currency='NOK'),
        dict(value=float(basis['tax_profit']), label='Næringsresultat i avgrenset omfang', datatype='Currency', currency='NOK')]
    return columns, rows, message, None, summary
