"""Norwegian native configuration, not a calculator or a posting engine.

Codes are classifications from Skatteetaten's MVA/SAF-T code list. Item Tax
Templates contain all ordinary VAT accounts, with explicit zeroes for other rates.
The native item override then supports mixed rates without a second journal.
"""
import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

CODE = 'custom_norway_vat_code'
SALES_CODE = 'custom_norway_sales_vat_code'
PURCHASE_CODE = 'custom_norway_purchase_vat_code'
RATE = 'custom_norway_vat_rate'
DEDUCTION = 'custom_norway_deduction_percent'
SALES_DOCUMENTS = ('Quotation', 'Sales Order', 'Delivery Note', 'Sales Invoice')
ORDINARY = ((25, '2700', '2710', '3', '1'), (15, '2701', '2711', '31', '11'),
            (12, '2703', '2713', '33', '13'))


def configure_fields():
    create_custom_fields({'Item Tax Template': [
        {'fieldname': SALES_CODE, 'label': 'Norwegian sales VAT code', 'fieldtype': 'Data',
         'insert_after': 'company'},
        {'fieldname': PURCHASE_CODE, 'label': 'Norwegian purchase VAT code', 'fieldtype': 'Data',
         'insert_after': SALES_CODE},
        {'fieldname': RATE, 'label': 'Norwegian VAT rate', 'fieldtype': 'Float',
         'insert_after': PURCHASE_CODE, 'read_only': 1},
        {'fieldname': DEDUCTION, 'label': 'Input VAT deduction percent', 'fieldtype': 'Percent',
         'insert_after': RATE, 'read_only': 1},
    ], **{doctype: [
        {'fieldname': CODE, 'label': 'Norwegian VAT code', 'fieldtype': 'Data',
         'insert_after': 'item_tax_template', 'read_only': 0, 'allow_on_submit': int(doctype in ('Sales Invoice Item', 'Purchase Invoice Item', 'Purchase Receipt Item')), 'no_copy': 0, 'print_hide': 1},
        {'fieldname': RATE, 'label': 'Norwegian VAT rate', 'fieldtype': 'Float',
         'insert_after': CODE, 'read_only': 1, 'no_copy': 0, 'print_hide': 1},
    ] for doctype in ('Sales Invoice Item', 'Purchase Invoice Item', 'Purchase Order Item', 'Purchase Receipt Item')}})
    create_custom_fields({doctype: [
        {'fieldname': DEDUCTION, 'label': 'Input VAT deduction percent', 'fieldtype': 'Percent',
         'insert_after': 'item_tax_template', 'default': '100', 'in_list_view': 1, 'print_hide': 1},
    ] for doctype in ('Purchase Invoice Item', 'Purchase Order Item', 'Purchase Receipt Item')})
    from erpnext_norway.vat_valuation import configure_fields as valuation_fields
    valuation_fields()


def seed(company, upgrade=False):
    from erpnext_norway.vat import FROM, STATUS
    if company.country != 'Norway' or company.get(STATUS) != 'Registered':
        return
    accounts = {code: frappe.db.get_value('Account', {'company': company.name,
        'account_number': code, 'is_group': 0}) for row in ORDINARY for code in row[1:3]}
    if not all(accounts.values()):
        return  # Retain explicit alternative charts; never guess tax accounts.
    for rate, output, input_, sales_code, purchase_code in ORDINARY:
        category = f'Norge MVA {rate} %'
        if not frappe.db.exists('Tax Category', category):
            frappe.get_doc({'doctype': 'Tax Category', 'title': category}).insert(ignore_permissions=True)
        for tax_type, code, title in (
            ('Sales', output, f'Utgående MVA {rate} %'),
            ('Purchase', input_, f'Inngående MVA {rate} % – fullt fradrag'),
        ):
            if upgrade and rate == 25:
                continue  # Existing 25% choices and intentionally removed rules stay untouched.
            doctype = f'{tax_type} Taxes and Charges Template'
            template = frappe.db.get_value(doctype, {'company': company.name,
                'tax_category': category, 'disabled': 0})
            if not template:
                template = frappe.get_doc({'doctype': doctype, 'company': company.name,
                    'title': title, 'tax_category': category, 'is_default': 0,
                    'taxes': [{'charge_type': 'On Net Total', 'account_head': accounts[code],
                        'description': f'MVA {rate} %', 'rate': rate, 'cost_center': company.cost_center,
                        'category': 'Total', 'add_deduct_tax': 'Add'}],
                }).insert(ignore_permissions=True).name
            rule_field = 'sales_tax_template' if tax_type == 'Sales' else 'purchase_tax_template'
            if not frappe.db.exists('Tax Rule', {'company': company.name, 'tax_type': tax_type,
                                                'tax_category': category}):
                frappe.get_doc({'doctype': 'Tax Rule', 'company': company.name, 'tax_type': tax_type,
                    'tax_category': category, rule_field: template, 'from_date': company.get(FROM),
                    'priority': 1}).insert(ignore_permissions=True)
        title = f'MVA {rate} % – varelinjer'
        if not frappe.db.exists('Item Tax Template', {'title': title, 'company': company.name}):
            frappe.get_doc({'doctype': 'Item Tax Template', 'company': company.name, 'title': title,
                SALES_CODE: sales_code, PURCHASE_CODE: purchase_code, RATE: rate, DEDUCTION: 100,
                'taxes': [{'tax_type': account, 'tax_rate': rate if code in (output, input_) else 0}
                          for code, account in accounts.items()],
            }).insert(ignore_permissions=True)

    for title, sales_code in (('Fritatt MVA – nullsats', '5'), ('Unntatt MVA', '6'),
                              ('Uten MVA-behandling', '7'), ('Eksport – fritatt MVA', '52')):
        if not frappe.db.exists('Item Tax Template', {'title': title, 'company': company.name}):
            frappe.get_doc({'doctype': 'Item Tax Template', 'company': company.name, 'title': title,
                SALES_CODE: sales_code, PURCHASE_CODE: '0', RATE: 0, DEDUCTION: 0,
                'taxes': [{'tax_type': account, 'tax_rate': 0} for account in accounts.values()],
            }).insert(ignore_permissions=True)

    from erpnext_norway.reverse_charge import seed as seed_reverse_charge
    seed_reverse_charge(company)


def stamp_codes(doc, method=None):
    from erpnext_norway.vat import posted_update, effective
    if posted_update(doc) or doc.get('is_return') or not doc.company:
        return
    company = frappe.get_cached_doc('Company', doc.company)
    if company.country != 'Norway':
        return
    sales = doc.doctype == 'Sales Invoice'
    field = SALES_CODE if sales else PURCHASE_CODE
    date = doc.get('posting_date') if sales else (doc.get('bill_date') or doc.get('posting_date') or doc.get('transaction_date'))
    category_codes = {f'Norge MVA {rate} %': sale if sales else purchase
                      for rate, _, _, sale, purchase in ORDINARY}
    from erpnext_norway.vat_quarterly import ITEM as QUARTERLY_ITEM
    for row in doc.items:
        if row.get(QUARTERLY_ITEM):
            row.set(CODE, '0')
            continue
        if row.item_tax_template:
            template = frappe.get_cached_doc('Item Tax Template', row.item_tax_template)
            code = template.get(field)
            row.set(RATE, template.get(RATE))
        elif not sales and foreign_header_code(doc):
            code = foreign_header_code(doc)
        elif not effective(company, date):
            code = '7' if sales else '0'
        else:
            code = category_codes.get(doc.tax_category)
            if not code and doc.taxes_and_charges:
                kind = 'Sales' if sales else 'Purchase'
                category = frappe.db.get_value(kind + ' Taxes and Charges Template',
                    doc.taxes_and_charges, 'tax_category')
                code = category_codes.get(category)
        if not row.item_tax_template:
            rate = next((rate for rate, *_ in ORDINARY if doc.tax_category == f'Norge MVA {rate} %'), 0)
            row.set(RATE, rate)
        if code == '85' and (doc.doctype != 'Purchase Receipt' or not effective(
                company, row.get('custom_norway_import_date') or date)):
            code = '20'  # Commercial cost is separate from the customs declaration basis.
        if sales and not effective(company, date):
            code = '7'
        row.set(CODE, code if code is not None else row.get(CODE))


def prepare_items(doc, method=None):
    """Configure native rates/expense rows; leave amounts and posting to core."""
    from erpnext_norway.vat import posted_update
    from frappe.utils import flt
    if posted_update(doc) or doc.get('is_return') or not doc.company:
        return
    if frappe.get_cached_value('Company', doc.company, 'country') != 'Norway':
        return
    from erpnext_norway.vat_quarterly import prepare as prepare_quarterly
    if doc.doctype in ('Purchase Invoice', 'Purchase Order'):
        prepare_quarterly(doc)
    from erpnext_norway.vat_currency import prepare as prepare_currency
    if doc.doctype in ('Purchase Invoice', 'Purchase Order'):
        prepare_currency(doc)
    doc.flags.norway_vat_cost_inclusions = {}
    doc.flags.norway_removed_input_taxes = []
    sales = doc.doctype in SALES_DOCUMENTS
    if sales and any(row.item_tax_template and frappe.get_cached_value(
            'Item Tax Template', row.item_tax_template, SALES_CODE) for row in doc.items):
        prepare_sales_rows(doc)
    for row in doc.items:
        if row.get('custom_norway_quarterly_service'):
            continue  # Source supplier amount stays untaxed; only the calculation copy uses its nominal rate.
        if not row.item_tax_template and not sales and row.get(DEDUCTION) not in (None, '', 100, 100.0, '100'):
            category = doc.tax_category
            if not category and doc.taxes_and_charges:
                category = frappe.db.get_value('Purchase Taxes and Charges Template',
                    doc.taxes_and_charges, 'tax_category')
            for rate, *_ in ORDINARY:
                if category == f'Norge MVA {rate} %':
                    row.item_tax_template = frappe.db.get_value('Item Tax Template', {
                        'company': doc.company, 'title': f'MVA {rate} % – varelinjer'})
                    break
        if not row.item_tax_template:
            continue
        template = frappe.get_cached_doc('Item Tax Template', row.item_tax_template)
        nominal = template.get(RATE)
        if sales:
            if nominal and template.get(SALES_CODE):
                append_native_rows(doc, row, template)
            continue
        if not nominal or not template.get(PURCHASE_CODE):
            continue  # Explicit native/site templates remain under their owner's control.
        raw_percent = row.get(DEDUCTION)
        percent = 100 if raw_percent in (None, '') else flt(raw_percent)
        configured_percent = template.get(DEDUCTION)
        if (configured_percent not in (None, 100) and percent == 100
                and doc.flags.get('norway_vat_deduction_row') != row.name):
            # Selecting a saved partial template must not silently turn into
            # full deduction because a new row carries the field's default 100.
            percent = flt(configured_percent)
            row.set(DEDUCTION, percent)
        if not 0 <= percent <= 100:
            frappe.throw(frappe._('Input VAT deduction must be between 0 and 100 percent.'))
        from erpnext_norway.reverse_charge import CODES as REVERSE_CODES, treatment, validate as validate_reverse
        reverse = template.get(PURCHASE_CODE) in REVERSE_CODES
        if reverse:
            OUTPUT, INPUT, with_deduction, without = treatment(nominal)
            validate_reverse(doc, row, template)
        if percent == 100:
            if template.get(DEDUCTION) != 100:
                base = frappe.db.get_value('Item Tax Template', {'company': doc.company,
                    'title': (f'Tjenestekjøp fra utlandet – MVA {nominal:g} % – 100 % fradrag' if reverse
                              else f'MVA {nominal:g} % – varelinjer')}, 'name')
                if not base:
                    frappe.throw(frappe._('Select an existing full-deduction item tax template before changing deduction to 100 percent.'))
                row.item_tax_template = base
                template = frappe.get_cached_doc('Item Tax Template', base)
            append_native_rows(doc, row, template)
            continue
        from erpnext_norway.vat_valuation import allocation_account
        account = allocation_account(doc, row)
        if any(tax.account_head == account.name and tax.charge_type != 'Actual'
                and float(tax.rate or 0) and not tax.get('set_by_item_tax_template') for tax in doc.taxes):
            frappe.throw(frappe._('An existing percentage charge uses the non-deductible VAT cost account. Use a separate charge account.'))
        # Native Item Tax Template validates account_type; this refines an untyped
        # expense account without changing its root, number, name or ledger values.
        if not account.account_type:
            account.account_type = 'Expense Account'
            account.save()
        code = (with_deduction if percent else without) if reverse else next((purchase for rate, _, _, _, purchase in ORDINARY if rate == nominal), None)
        title = (f'Tjenestekjøp fra utlandet – MVA {nominal:g} %' if reverse else f'Inngående MVA {nominal:g} %') + f' – {percent:g} % fradrag – {account.account_number or account.account_name}'
        name = frappe.db.get_value('Item Tax Template', {'company': doc.company, 'title': title})
        if not name:
            rates = {tax.tax_type: 0 for tax in template.taxes}
            vat_account = frappe.db.get_value('Account', {'company': doc.company,
                'account_number': INPUT if reverse else next(input_ for rate, _, input_, _, _ in ORDINARY if rate == nominal)})
            if reverse:
                output = frappe.db.get_value('Account', {'company': doc.company, 'account_number': OUTPUT})
                rates[output] = nominal
            rates[vat_account] = nominal * percent / 100
            rates[account.name] = nominal * (100 - percent) / 100
            name = frappe.get_doc({'doctype': 'Item Tax Template', 'company': doc.company,
                'title': title, PURCHASE_CODE: code if percent or reverse else '0', RATE: nominal, DEDUCTION: percent,
                'taxes': [{'tax_type': key, 'tax_rate': value} for key, value in rates.items()],
            }).insert().name
        row.item_tax_template = name
        chosen = frappe.get_cached_doc('Item Tax Template', name)
        if reverse:
            validate_reverse(doc, row, chosen)
            if chosen.get(DEDUCTION) != percent:
                frappe.throw(frappe._('The saved item tax template no longer matches the selected deduction. Review its native rates.'))
        append_native_rows(doc, row, chosen)


def prepare_sales_rows(doc):
    """Remove only native auto-input rows from shared Norwegian item templates."""
    rows = list(doc.taxes)
    remove = set()
    for position, tax in enumerate(rows, 1):
        number = frappe.get_cached_value('Account', tax.account_head, 'account_number') if tax.account_head else ''
        if not (number or '').startswith('271'):
            continue
        if not (tax.get('set_by_item_tax_template') and tax.charge_type == 'On Net Total'
                and not tax.rate and not tax.included_in_print_rate):
            frappe.throw(frappe._('Use output VAT accounts on sales documents. Review the tax rows.'))
        remove.add(position)
    if not remove:
        return
    positions = {old: new for new, old in enumerate(
        (position for position in range(1, len(rows) + 1) if position not in remove), 1)}
    for position, tax in enumerate(rows, 1):
        if position in remove:
            doc.flags.norway_removed_input_taxes.append(tax.name)
            doc.remove(tax)  # Native child removal retains ordinary row indexing.
        elif (tax.charge_type or '').startswith('On Previous Row'):
            reference = frappe.utils.cint(tax.row_id)
            if reference in remove:
                frappe.throw(frappe._('A sales tax row refers to an input VAT row. Review its native row reference.'))
            if reference in positions:
                tax.row_id = str(positions[reference])


def append_native_rows(doc, item, template):
    """Use core's row creation; adapt only Norwegian direction/basis metadata."""
    from erpnext.controllers.accounts_controller import add_taxes_from_tax_template
    from erpnext_norway.reverse_charge import CODES as REVERSE_CODES, treatment
    sales = doc.doctype in SALES_DOCUMENTS
    reverse = not sales and template.get(PURCHASE_CODE) in REVERSE_CODES
    OUTPUT, INPUT = treatment(template.get(RATE))[:2] if reverse else (None, None)
    from erpnext_norway.vat_currency import KIND, foreign
    base_kind = KIND if reverse and foreign(doc) else 'On Net Total'
    prefix = '270' if sales else '271'
    included = next((tax.included_in_print_rate for tax in doc.taxes
                     if tax.account_head and frappe.get_cached_value('Account', tax.account_head,
                         'account_type') == 'Tax'), 0)
    for row in template.taxes:
        if not row.tax_rate:
            continue
        account = frappe.get_cached_doc('Account', row.tax_type)
        expense = not sales and account.root_type == 'Expense'
        if not ((account.account_number or '').startswith(prefix) or expense or
                (reverse and account.account_number == OUTPUT)):
            continue
        if reverse and any(tax.included_in_print_rate for tax in doc.taxes):
            frappe.throw(frappe._('Reverse-charge VAT must not be included in the supplier price.'))
        if reverse and account.account_number in (OUTPUT, INPUT):
            direction = 'Deduct' if account.account_number == OUTPUT else 'Add'
            for existing_row in (tax for tax in doc.taxes if tax.account_head == account.name):
                if existing_row.add_deduct_tax != direction or existing_row.category != 'Total':
                    if not existing_row.get('set_by_item_tax_template'):
                        frappe.throw(frappe._('Keep output reverse-charge VAT as Deduct and input VAT as Add in the native tax rows.'))
                    existing_row.add_deduct_tax = direction
                    existing_row.category = 'Total'
        percentage = ('On Net Total', 'On Previous Row Amount', 'On Previous Row Total', KIND)
        if expense:
            nominal_input = INPUT if reverse else next(input_ for rate, _, input_, _, _ in ORDINARY if rate == template.get(RATE))
            input_account = frappe.db.get_value('Account', {'company': doc.company, 'account_number': nominal_input})
            sources = [tax for tax in doc.taxes if tax.account_head == input_account]
            if any(tax.charge_type not in percentage for tax in sources):
                frappe.throw(frappe._('Item-level VAT treatment requires native percentage VAT rows.'))
            # Mirror the native VAT bases, including VAT on freight/insurance.
            # Core calculates each percentage; this only configures counterpart rows.
            bases = [(tax.charge_type, tax.get('row_id')) for tax in sources] or [(base_kind, None)]
            if sources and not any(tax.charge_type in ('On Net Total', 'On Previous Row Total', KIND) for tax in sources):
                bases.append((base_kind, None))
        else:
            existing = [tax for tax in doc.taxes if tax.account_head == account.name]
            if any(tax.charge_type not in percentage for tax in existing):
                frappe.throw(frappe._('Item-level VAT treatment requires native percentage VAT rows.'))
            if any(tax.charge_type in ('On Net Total', 'On Previous Row Total', KIND) for tax in existing):
                continue  # Previous Row Total already includes the goods' net amount.
            bases = [(base_kind, None)]
        for kind, reference in bases:
            matching_basis = next((tax for tax in sources if tax.charge_type == kind and
                (kind == 'On Net Total' or str(tax.get('row_id') or '') == str(reference or ''))), None) if expense else None
            basis_included = matching_basis.included_in_print_rate if matching_basis else included
            if expense:
                key = (account.name, kind, str(reference or '') if kind != 'On Net Total' else '')
                seen = doc.flags.norway_vat_cost_inclusions
                if key in seen and seen[key] != basis_included:
                    frappe.throw(frappe._('VAT inclusion must match for lines sharing a VAT cost account and tax basis.'))
                seen[key] = basis_included
            existing_row = next((tax for tax in doc.taxes if tax.account_head == account.name and tax.charge_type == kind
                and (kind == 'On Net Total' or str(tax.get('row_id') or '') == str(reference or ''))), None)
            if existing_row:
                if expense and existing_row.get('custom_norway_vat_cost'):
                    existing_row.included_in_print_rate = basis_included
                continue
            values = {'charge_type': kind, 'row_id': reference, 'account_head': account.name,
                'description': ('Ikke-fradragsberettiget MVA' if expense else
                    (f'Utgående MVA {template.get(RATE):g} % – omvendt avgiftsplikt' if account.account_number == OUTPUT else
                     f'Inngående MVA {template.get(RATE):g} % – tjenestekjøp fra utlandet') if reverse else f'MVA {template.get(RATE):g} %'),
                'rate': 0, 'category': 'Valuation and Total' if account.account_type == 'Expenses Included In Valuation' else 'Total', 'add_deduct_tax': 'Deduct' if reverse and account.account_number == OUTPUT else 'Add',
                'custom_norway_vat_cost': int(expense),
                'cost_center': item.get('cost_center') or doc.get('cost_center') or
                    frappe.get_cached_value('Company', doc.company, 'cost_center'), 'included_in_print_rate': basis_included,
                'set_by_item_tax_template': 1}
            if not any(tax.account_head == account.name for tax in doc.taxes):
                # The shared Norwegian template contains both sales and purchase
                # accounts. Pass only this transaction's account to core, with
                # rate zero: the real per-item rates stay in Item Tax Template.
                before = len(doc.taxes)
                add_taxes_from_tax_template(frappe._dict(
                    item_tax_rate=frappe.as_json({account.name: 0})), doc, db_insert=False)
                if len(doc.taxes) == before:
                    frappe.throw(frappe._('Enable Automatically add Taxes and Charges from Item Tax Template in Accounts Settings, or configure the required tax rows explicitly.'))
                doc.taxes[-1].update(values)
            else:
                # Core detects duplicates by account alone. A second basis on
                # that account (net plus freight) needs one additional row.
                if not frappe.get_single_value('Accounts Settings', 'add_taxes_from_item_tax_template'):
                    frappe.throw(frappe._('Enable Automatically add Taxes and Charges from Item Tax Template in Accounts Settings, or configure the required tax rows explicitly.'))
                doc.append('taxes', values)


def move_seed_dates(company, previous):
    """Move unchanged native 15/12 seed ranges when the confirmed date changes."""
    from erpnext_norway.vat import FROM
    if not previous or not previous.get(FROM) or previous.get(FROM) == company.get(FROM):
        return
    selectors = ('customer', 'customer_group', 'supplier', 'supplier_group', 'item', 'item_group',
        'billing_city', 'billing_county', 'billing_state', 'billing_zipcode', 'billing_country',
        'shipping_city', 'shipping_county', 'shipping_state', 'shipping_zipcode', 'shipping_country')
    for rate, *_ in ORDINARY[1:]:
        for name in frappe.get_all('Tax Rule', filters={'company': company.name,
                'tax_category': f'Norge MVA {rate} %'}, pluck='name'):
            rule = frappe.get_doc('Tax Rule', name)
            if (rule.priority == 1 and not rule.to_date
                    and str(rule.from_date) == str(previous.get(FROM))
                    and not any(rule.get(field) for field in selectors)):
                rule.from_date = company.get(FROM)
                rule.save(ignore_permissions=True)


@frappe.whitelist()
def preview_items(document, deduction_row=None, template_row=None):
    """Prepare ordinary form choices; native browser controller calculates totals."""
    doc = frappe.get_doc(frappe.parse_json(document))
    if doc.doctype not in (*SALES_DOCUMENTS, 'Purchase Invoice', 'Purchase Order', 'Purchase Receipt'):
        frappe.throw(frappe._('Invalid invoice type.'))
    doc.check_permission('create' if doc.is_new() else 'write')
    frappe.get_doc('Company', doc.company).check_permission('read')
    if doc.docstatus != 0:
        frappe.throw(frappe._('Only draft invoices can be changed.'))
    doc.flags.norway_vat_deduction_row = deduction_row
    if doc.doctype not in SALES_DOCUMENTS and template_row:
        for row in doc.items:
            if row.name == template_row and row.item_tax_template:
                percent = frappe.db.get_value('Item Tax Template', row.item_tax_template, DEDUCTION)
                if percent is not None:
                    row.set(DEDUCTION, percent)
    if doc.get('is_return'):
        if doc.doctype == 'Purchase Receipt':
            from erpnext_norway.vat_valuation import prepare_receipt_return
            prepare_receipt_return(doc)
        elif doc.doctype in ('Purchase Invoice', 'Sales Invoice'):
            from erpnext_norway.vat_returns import prepare
            prepare(doc)
            if doc.doctype == 'Purchase Invoice':
                from erpnext_norway.vat_valuation import link_credit_receipts
                link_credit_receipts(doc)
    from erpnext_norway.vat_currency import foreign, reverse_item, DATE, EXCHANGE
    if (not doc.get('is_return') and doc.doctype in ('Purchase Invoice', 'Purchase Order')
            and foreign(doc) and any(reverse_item(doc, row) for row in doc.items)
            and any(not reverse_item(doc, row) or not row.get(DATE) or not row.get(EXCHANGE)
                    for row in doc.items)):
        # Native item/price callbacks run while a new row is still incomplete.
        # Defer the adapter until normal line selection is complete; save still
        # validates every required source field through the ordinary event.
        return {'items': [], 'taxes': [], 'pending_currency': True}
    prepare_items(doc)
    from erpnext_norway.vat_valuation import guard_configuration
    guard_configuration(doc)
    fields = ['item_tax_template', DEDUCTION, 'custom_norway_quarterly_service']
    if doc.doctype == 'Purchase Receipt':
        stamp_codes(doc)
        fields += [CODE, RATE]
    if doc.get('is_return'):
        from erpnext_norway.vat_currency import DATE, EXCHANGE
        fields += ['is_fixed_asset', 'custom_norway_quarterly_service', DATE, EXCHANGE, CODE, RATE, 'purchase_invoice', 'purchase_invoice_item', 'purchase_receipt', 'pr_detail']
    return {'return_type': doc.get('custom_norway_vat_return_type'),
            'removed_taxes': doc.flags.get('norway_removed_input_taxes') or [],
            'items': [{'name': row.name, **{field: row.get(field) for field in fields}}
                      for row in doc.items], 'taxes': [row.as_dict() for row in doc.taxes]}


def validate_code_changes(doc, method=None):
    """Native allow-on-submit metadata correction, audited by native Version.

    Classification can be completed on legacy invoices without changing amounts,
    tax rows or original PDFs. Economic corrections still need native credit notes.
    """
    previous = doc.get_doc_before_save()
    from erpnext_norway.vat_quarterly import ITEM as QUARTERLY_ITEM
    old_rows = {row.name: row for row in previous.items} if previous else {}
    for row in doc.items:
        original = old_rows.get(row.name)
        if original and original.get(QUARTERLY_ITEM) and (row.get(CODE) or None) != (original.get(CODE) or None):
            frappe.throw(frappe._('Correct the source purchase or credit note to update its quarterly VAT adjustment.'))
    old = {name: row.get(CODE) for name, row in old_rows.items()}
    for row in doc.items:
        if (row.get(CODE) or None) != (old.get(row.name) or None):
            check_metadata_period(doc)
            check_code(doc, row)


def check_code(doc, item):
    from erpnext_norway.vat import is_vat_account
    code = item.get(CODE)
    sales = doc.doctype == 'Sales Invoice'
    expected = ({'3': '2700', '31': '2701', '33': '2703'} if sales else
        {'1': '2710', '11': '2711', '13': '2713', '86': '2704', '87': '2704',
         '88': '2709', '89': '2709', '81': '2705', '82': '2705', '83': '2706',
         '84': '2706', '14': '2715', '15': '2716'})
    zero_codes = {'5', '6', '7', '52'} if sales else {'0', '20', '21', '22', '85'}
    if code not in expected and code not in zero_codes:
        frappe.throw(frappe._('Select a supported Norwegian VAT code for this invoice line.'))
    previous = doc.get_doc_before_save()
    memory = doc.get('_item_wise_tax_details') if not previous or previous.docstatus != 1 else None
    if memory:
        active = [detail.tax for detail in memory if detail.item is item
                  and (abs(float(detail.amount or 0)) > 0.000001 or float(detail.rate or 0))
                  and is_vat_account(detail.tax.account_head)]
    else:
        details = frappe.get_all('Item Wise Tax Detail', filters={'parent': doc.name,
            'parenttype': doc.doctype, 'item_row': item.name}, fields=['tax_row', 'amount', 'rate'])
        taxes = {tax.name: tax for tax in doc.taxes}
        active = [taxes[detail.tax_row] for detail in details if detail.tax_row in taxes
                  and (abs(float(detail.amount or 0)) > 0.000001 or float(detail.rate or 0))
                  and is_vat_account(taxes[detail.tax_row].account_head)]
    numbers = {frappe.get_cached_value('Account', tax.account_head, 'account_number') for tax in active}
    valid = (not active) if code in zero_codes else (expected[code] in numbers)
    if code in {'3', '31', '33', '1', '11', '13', '14', '15'}:
        valid = numbers == {expected[code]}
    input_accounts = {'86': '2714', '88': '2718', '81': '2715', '83': '2716'}
    if code in input_accounts:
        valid = numbers == {expected[code], input_accounts[code]}
    if code in {'87', '89', '82', '84'}:
        valid = numbers == {expected[code]}
    if not valid and not active and not float(item.base_net_amount or 0):
        valid = True  # Zero-price lines may still have a taxable classification.
    if not valid:
        frappe.throw(frappe._('The VAT code does not match the invoice line tax posting. Use a credit note for amount corrections.'))


def check_metadata_period(doc):
    from erpnext.accounts.general_ledger import (
        validate_accounting_period, check_freezing_date, validate_against_pcv,
    )
    validate_accounting_period([frappe._dict(posting_date=doc.posting_date,
        company=doc.company, voucher_type=doc.doctype)])
    check_freezing_date(doc.posting_date, doc.company)
    validate_against_pcv(doc.get('is_opening') or 'No', doc.posting_date, doc.company)


def validate_invoice_codes(doc, method=None):
    if frappe.get_cached_value('Company', doc.company, 'country') != 'Norway':
        return
    for row in doc.items:
        check_code(doc, row)


def foreign_header_code(doc):
    numbers = {frappe.get_cached_value('Account', tax.account_head, 'account_number')
               for tax in doc.taxes if tax.account_head and float(tax.rate or 0)}
    for output, input_, with_deduction, without in (
        ('2704', '2714', '86', '87'), ('2709', '2718', '88', '89'),
        ('2705', '2715', '81', '82'), ('2706', '2716', '83', '84'),
    ):
        if output in numbers:
            return with_deduction if input_ in numbers else without
