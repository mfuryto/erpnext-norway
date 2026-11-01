"""Format qualified native customs journals; never calculate or create postings."""
from collections import defaultdict
from decimal import Decimal

import frappe

from erpnext_norway import saft_builder as xml
from erpnext_norway.vat_catalog import CODE, RATE, DEDUCTION
from erpnext_norway.vat_journal import BASE, SPEC


def journal_taxes(doc, rows):
    from erpnext_norway.saft import unsupported
    from erpnext_norway.vat import is_vat_account

    def reject(reason='Importbilagets grunnlag, fradrag eller MVA-linjer er ikke entydige.'):
        unsupported(doc, reason)

    outputs = [r for r in doc.accounts if frappe.get_cached_value('Account', r.account, 'account_number') in {'2705', '2706'}]
    if len(outputs) != 1:
        reject()
    output = outputs[0]
    code = output.get(CODE)
    qualified = {'81': (25, '2705', '2715'), '82': (25, '2705', None),
                 '83': (15, '2706', '2716'), '84': (15, '2706', None)}.get(code)
    if not qualified:
        reject()
    rate, output_number, input_number = qualified
    recorded_base = Decimal(str(output.get(BASE) or 0))
    base = xml._money(recorded_base)
    if base != recorded_base:
        reject('Deklarasjonens MVA-grunnlag må være registrert i hele øre; eksporten avrunder ikke kilden.')
    share = Decimal(str(output.get(DEDUCTION) or 0))
    if not base or not Decimal(0) <= share <= Decimal(100) or (
            (input_number and not share) or (not input_number and share)):
        reject('Registrer dokumentert fradragsandel på utgående innførsels-MVA; eldre bilag blir ikke gitt en antatt andel.')
    if frappe.get_cached_value('Account', output.account, 'account_number') != output_number:
        reject()
    inputs = [r for r in doc.accounts if is_vat_account(r.account) and r is not output]
    if len(inputs) > 1 or (inputs and (not input_number or
            frappe.get_cached_value('Account', inputs[0].account, 'account_number') != input_number)):
        reject()
    input_ = inputs[0] if inputs else None
    vat_rows = [output] + ([input_] if input_ else [])
    for item in vat_rows:
        if (item.get(CODE) != code or Decimal(str(item.get(RATE) or 0)) != rate or
                item.account_currency != 'NOK' or item.get(SPEC) or
                (item is not output and (item.get(DEDUCTION) or xml._money(item.get(BASE) or 0) not in (Decimal(), base))) or
                bool(item.debit) == bool(item.credit)):
            reject()
    out = xml._money(output.debit) - xml._money(output.credit)
    inc = xml._money(input_.debit) - xml._money(input_.credit) if input_ else Decimal()
    if (base > 0) != (out < 0) or inc * out > 0 or abs(inc) > abs(out):
        reject()
    costs = [r for r in doc.accounts if not is_vat_account(r.account)]
    bases = [r for r in costs if r.get(CODE) == code]
    if len(bases) != 2 or len({r.account for r in costs}) != 1:
        reject('Bruk dokumenterte, balanserende grunnlagsføringer på én kostnadskonto.')
    account = bases[0].account
    if frappe.get_cached_value('Account', account, 'root_type') != 'Expense':
        reject()
    dimension = (bases[0].cost_center, bases[0].project)
    for item in costs:
        if (item.account_currency != 'NOK' or item.party or item.get(SPEC) or item.get(BASE) or
                item.get(DEDUCTION) or (item.cost_center, item.project) != dimension or
                bool(item.debit) == bool(item.credit)):
            reject()
        if item in bases:
            if Decimal(str(item.get(RATE) or 0)) != rate or abs(xml._money(item.debit) - xml._money(item.credit)) != abs(base):
                reject()
        elif item.get(CODE) not in (None, '', '0'):
            reject()
    if not (sum(xml._money(r.debit) for r in bases) == sum(xml._money(r.credit) for r in bases) == abs(base)):
        reject()
    if sum((xml._money(r.debit) - xml._money(r.credit) for r in costs), Decimal()) != -(out + inc):
        reject()

    # Core gives cancellation counters an exact, stable remark. Do not infer
    # their identity from timestamps or manufacture a missing gross counter.
    stages = defaultdict(list)
    marker = 'On cancellation of ' + doc.name
    for row in rows:
        if row.party or row.account_currency != 'NOK' or row.transaction_currency not in (None, '', 'NOK'):
            reject()
        stages[row.remarks == marker].append(row)
    if not stages or (True in stages and doc.docstatus != 2):
        reject()
    result = defaultdict(list)
    for cancelled, entries in stages.items():
        sign = -1 if cancelled else 1
        if len({r.posting_date for r in entries}) != 1:
            reject()
        actual_vat = [r for r in entries if is_vat_account(r.account)]
        if len(actual_vat) != len(vat_rows):
            reject()
        for item in vat_rows:
            matched = [r for r in actual_vat if r.account == item.account]
            if len(matched) != 1:
                reject()
            native = matched[0]
            debit, credit = xml._money(item.debit), xml._money(item.credit)
            if cancelled:
                debit, credit = credit, debit
            if (xml._money(native.debit), xml._money(native.credit)) != (debit, credit):
                reject('Importbilagets MVA-linjer stemmer ikke med hovedboken.')
        actual_costs = [r for r in entries if not is_vat_account(r.account)]
        if any(r.account != account or (r.cost_center, r.project) != dimension for r in actual_costs):
            reject()
        expected = tuple(sum((xml._money(r.get(side)) for r in costs), Decimal()) for side in ('debit', 'credit'))
        if cancelled:
            expected = expected[::-1]
        actual = tuple(sum((xml._money(r.get(side)) for r in actual_costs), Decimal()) for side in ('debit', 'credit'))
        if actual != expected:
            reject('Bokførte brutto grunnlagsføringer mangler, for eksempel etter nettet kansellering. Eksporten lager ikke erstatningsposteringer.')
        # Input and output VAT are on their respective booked basis sides.
        # The zero-input case retains an explicit zero on the opposite side.
        out_credit = out * sign < 0
        for line_credit, amount in ((out_credit, abs(out)), (not out_credit, abs(inc))):
            side = 'credit' if line_credit else 'debit'
            candidates = [r for r in actual_costs if xml._money(r.get(side)) == abs(base)]
            combined = [r for r in actual_costs if r.debit and r.credit]
            if combined:
                if len(actual_costs) != 1:
                    reject()
                candidates = combined
            if len(candidates) != 1:
                reject('Entydig bokført grunnlagslinje mangler for innførsels-MVA.')
            result[candidates[0].name].append(xml.TaxInformation(code, abs(base), amount,
                tax_credit=line_credit, line_credit=line_credit))
    return result, {code: xml.TaxMapping(code, Decimal(rate), code, (share,))}
