"""Tax reconciliation, using native Profit and Loss and Trial Balance reports."""
import frappe
from erpnext_norway.enk_tax import collect


def execute(filters=None):
    filters = frappe._dict(filters or {})
    if not filters.company or not filters.fiscal_year:
        frappe.throw('Velg foretak og regnskapsår.')
    basis = collect(filters.company, filters.fiscal_year)
    rows = []

    def add(section, label, amount=None, account=None, **values):
        rows.append(dict(section=section, description=label,
            amount=float(amount) if amount is not None else None, account=account, **values))

    for field, label in [('book_income', 'Bokførte inntekter'), ('book_expenses', 'Bokførte kostnader'),
            ('book_profit', 'Bokført årsresultat'), ('book_depreciation', 'Tilbakeføring av bokførte avskrivninger'),
            ('tax_depreciation', 'Fradrag for skattemessige saldoavskrivninger'),
            ('non_saldo_deduction', 'Dokumenterte skattefradrag for driftsmidler utenfor saldo'),
            ('book_disposal', 'Tilbakeføring av bokført gevinst/tap ved driftsmiddelsalg'),
            ('tax_income', 'Skattepliktig inntekt fra saldo og direkte inntektsført salgsvederlag')]:
        sign = -1 if field in {'tax_depreciation', 'non_saldo_deduction', 'book_disposal'} else 1
        add('Resultatavstemming', label, sign * basis[field])
    for row in basis['corrections']:
        add('Skattekorreksjoner', row['reason'] + ' — ' + row['reference'], row['amount'], row['account'])
    gain_loss = basis['gain_loss']
    for field, label in [('opening', 'Inngående gevinst-/tapskonto'), ('transfers', 'Overført fra realiserte skattesaldoer'),
            ('income', 'Inntektsføring fra gevinst-/tapskonto'), ('deduction', 'Fradrag fra gevinst-/tapskonto'),
            ('closing', 'Utgående gevinst-/tapskonto')]:
        add('Gevinst- og tapskonto', label, gain_loss[field])
    add('Resultatavstemming', 'Beregnet næringsresultat', basis['tax_profit'])
    tax_closing = sum(p.closing_balance for p in basis['pools'])
    add('Verdiavstemming', 'Bokført nettoverdi anleggsmidler', basis['book_assets'])
    add('Verdiavstemming', 'Utgående skattesaldo (negativ saldo vises med minus)', tax_closing)
    add('Verdiavstemming', 'Bokført nettoverdi minus skattesaldo', basis['book_assets'] - tax_closing)
    for pool in basis['pools']:
        section = 'Saldogruppe ' + pool.group.value + (' — ' + pool.unit if pool.unit else '')
        for field, label in [('opening_balance', 'Inngående skattesaldo'), ('acquisitions', 'Årets netto tilgang'),
                ('disposal_proceeds', 'Årets salgsvederlag'), ('disposal_proceeds_taken_to_income', 'Direkte inntektsført vederlag'),
                ('balance_before_year_end_adjustments', 'Saldo før årets avskrivning/inntektsføring'),
                ('depreciation_deduction', 'Skattemessig avskrivning'), ('negative_balance_income', 'Inntektsført negativ saldo'),
                ('gain_loss_transfer', 'Overført til gevinst-/tapskonto (gevinst positiv)'),
                ('closing_balance', 'Utgående skattesaldo')]:
            add(section, label, getattr(pool, field))
    for post in basis['annual_posts']:
        assessed = post['tax_assessed']
        add('Næringsposter — bokført', post['code'] + ' ' + post['label'], post['book'],
            tax_opening=float(post['tax_opening']) if assessed else None,
            tax_closing=float(post['tax_closing']) if assessed else None)
    if filters.get('show_accounts', 1):
        for row in basis['annual_accounts']:
            values = {k: float(row[k]) if row[k] is not None else None
                for k in ('opening', 'debit', 'credit', 'closing', 'tax_opening', 'tax_closing', 'wealth')}
            add('Kontogrunnlag', (row['code'] + ' ' + row['label']).strip() +
                (' — ' + row['reference'] if row['reference'] else ''), row['book'], row['account'], **values)
    for row in basis['owner_movements']:
        add('Eierbevegelser — hovedbok', str(row['posting_date']), row['amount'], row['account'],
            source_type=row['doctype'], source=row['name'])
    for row in basis['person_items']:
        add('Personinntekt — dokumenterte poster', frappe._(row['role']) + ' — ' + row['reference'], row['amount'], row['account'])
    add('Personinntekt — grunnlag', 'Kapitalgrunnlag før all gjeld', basis['capital_return_base_gross'])
    add('Personinntekt — grunnlag', 'Netto skjermingsgrunnlag', basis['shielding_base_net'])
    add('Personinntekt — grunnlag', 'Kvalifiserende foretaksgjeld', basis['qualifying_business_debt'])
    if basis['person_income']:
        for field, label in [('business_profit', 'Skattemessig næringsresultat'),
                ('capital_income_deduction', 'Fradrag for kapitalinntekter og finansgevinster'),
                ('capital_cost_addback', 'Tilbakeførte kapitalkostnader, tap og særskilte fradrag'),
                ('interest_addback', 'Tilbakeførte renter etter gjeldsavgrensning'),
                ('shielding', 'Dokumentert skjermingsfradrag'),
                ('person_income_before_carryforward', 'Personinntekt før fremføring'),
                ('carried_forward_negative_used', 'Brukt negativ personinntekt fra tidligere år'),
                ('person_income', 'Beregnet personinntekt'),
                ('remaining_negative_carryforward', 'Negativ personinntekt til fremføring')]:
            add('Personinntekt — beregning', label, basis['person_income'][field])
    for issue in basis['issues']:
        add('Må vurderes før innlevering', issue)
    columns = [dict(fieldname='section', label='Del', fieldtype='Data', width=180),
        dict(fieldname='description', label='Forklaring', fieldtype='Data', width=490),
        dict(fieldname='amount', label='Beløp (NOK)', fieldtype='Currency', options='NOK', width=160),
        dict(fieldname='account', label='Konto', fieldtype='Link', options='Account', width=210)]
    columns += [dict(fieldname=field, label=label, fieldtype='Currency', options='NOK', width=150)
        for field, label in [('opening', 'Bokført IB'), ('debit', 'Debet'), ('credit', 'Kredit'),
            ('closing', 'Bokført UB'), ('tax_opening', 'Skatteverdi IB'), ('tax_closing', 'Skatteverdi UB'),
            ('wealth', 'Formuesverdi før rabatt')]]
    columns += [dict(fieldname='source_type', label='Bilagstype', fieldtype='Link', options='DocType', width=150),
        dict(fieldname='source', label='Bilag', fieldtype='Dynamic Link', options='source_type', width=180)]
    message = ('Årsgrunnlag for norsk ENK uten ansatte, NOK og 2026. Skatteopplysninger: '
        + frappe.utils.escape_html(basis['document']) + '. '
        'Næringspostene viser bokførte beløp; skattekorreksjonene vises i resultatavstemmingen. '
        'Kontolinjer bruker debet minus kredit; næringsposter følger postens fortegn. '
        'Tomme skatte-/formuesverdier er ikke vurdert. Formuesverdier er før portalens rabatt og gjeldsreduksjon. '
        'Skjerming krever dokumentert årsbeløp eller uttrykkelig valg om ikke å kreve fradrag. '
        'Dette er grunnlag for utfylling i Skatteetatens portal, ikke full personlig skatteberegning eller innsending.')
    summary = [dict(value=float(basis['book_profit']), label='Bokført årsresultat', datatype='Currency', currency='NOK'),
        dict(value=float(basis['tax_profit']), label='Beregnet næringsresultat', datatype='Currency', currency='NOK')]
    return columns, rows, message, None, summary
