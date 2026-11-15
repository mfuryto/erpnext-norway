"""Tax meaning on ordinary native journal rows; all posting remains native."""
import frappe

EFFECT = 'custom_norway_asset_tax_effect'
PROCEEDS = 'custom_norway_asset_tax_proceeds'
EFFECTS = {'New tax basis', 'Cost correction', 'Tax-neutral transfer', 'Disposal', 'Book asset gain or loss'}


def configure():
    from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
    create_custom_fields({'Journal Entry Account': [
        {'fieldname': EFFECT, 'label': 'Norwegian asset tax effect', 'fieldtype': 'Select',
            'options': '\n'+'\n'.join(sorted(EFFECTS)), 'insert_after': 'reference_name',
            'description': 'Use for documented asset movements in a manual journal. Native Asset references identify individual tax balances.'},
        {'fieldname': PROCEEDS, 'label': 'Tax disposal value excluding VAT', 'fieldtype': 'Currency',
            'options': 'Company:company:default_currency', 'insert_after': EFFECT,
            'depends_on': "eval:doc.custom_norway_asset_tax_effect==='Disposal'"},
    ]})


def validate(doc, method=None):
    tagged = [r for r in doc.accounts if r.get(EFFECT)]
    if not tagged:
        return
    company = frappe.get_cached_doc('Company', doc.company)
    if company.country != 'Norway' or company.default_currency != 'NOK' or not (doc.user_remark or '').strip():
        frappe.throw('Skattemessig driftsmiddelbevegelse krever norsk NOK-foretak og forklaring på det ordinære bilaget.')
    from erpnext_norway.enk_tax import number
    for row in tagged:
        kind = row.get(EFFECT)
        root, account_type = frappe.get_cached_value('Account', row.account, ['root_type','account_type'])
        if kind not in EFFECTS or (kind == 'Book asset gain or loss' and root not in {'Income','Expense'}) or (kind != 'Book asset gain or loss' and root != 'Asset'):
            frappe.throw('Velg skattemessig effekt som passer til bilagets faktiske konto.')
        if number(row.get(PROCEEDS)) < 0 or kind != 'Disposal' and number(row.get(PROCEEDS)):
            frappe.throw('Realisasjonsverdi brukes bare ved avgang og må være positiv eller null.')


def allocations(doc, gl, pools, selected, number, money):
    from erpnext_norway.enk_assets import pool_key
    from collections import defaultdict
    from decimal import Decimal
    validate(doc)
    adds = defaultdict(lambda: Decimal(0));proceeds = defaultdict(lambda: Decimal(0));quantities = defaultdict(lambda: Decimal(0))
    assigned = set().union(*selected.values()) if selected else set()
    actual = {name: sum((number(r.debit)-number(r.credit) for r in gl if r.account==name),Decimal(0)) for name in assigned}
    declared = defaultdict(lambda: Decimal(0));book_result=Decimal(0);gain_accounts=set()
    for row in doc.accounts:
        kind=row.get(EFFECT)
        if kind=='Book asset gain or loss':
            book_result += number(row.credit)-number(row.debit);gain_accounts.add(row.account)
        if row.account not in assigned:
            continue
        if not kind:
            frappe.throw('Skattesaldoen har en kilde som ikke er kvalifisert: angi skattemessig effekt på det ordinære bokføringsbilaget.')
        candidates=[p for p in pools if row.account in selected[pool_key(p)]]
        if row.reference_type=='Asset':
            candidates=[p for p in candidates if not p.get('asset') or p.asset==row.reference_name]
        if len(candidates)!=1:
            frappe.throw('Bilagslinjen krever én entydig skattesaldo og eventuell nativ driftsmiddelreferanse.')
        key=pool_key(candidates[0]);amount=number(row.debit)-number(row.credit)
        declared[row.account]+=amount
        if kind in {'New tax basis','Cost correction'}:adds[key]+=amount
        elif kind=='Disposal':proceeds[key]+=number(row.get(PROCEEDS));quantities[key]+=1
        elif kind!='Tax-neutral transfer':frappe.throw('Velg en gyldig skattemessig driftsmiddelbevegelse.')
    for name,value in actual.items():
        if money(value)!=money(declared[name]):frappe.throw('Skattemerkede bilagslinjer stemmer ikke med den native hovedboken.')
    return dict(adds=adds,proceeds=proceeds,quantities=quantities,book_result=book_result,accounts=gain_accounts)
