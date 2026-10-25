"""Native foreign tax amount/base/rounding probe and unsupported-flow guard.

Core calculates the probe; actual saves exercise the ordinary app event.
All documents and configuration are rolled back; no posting bypasses.
"""
import os
import frappe
os.chdir('/home/frappe/frappe-bench/sites')
frappe.init(site='accounting',sites_path='/home/frappe/frappe-bench/sites');frappe.connect()
frappe.set_user('Administrator')
from erpnext_norway.vat_catalog import CODE
from erpnext_norway.erpnext_norway.report.norsk_mva_spesifikasjon.norsk_mva_spesifikasjon import collect

MESSAGE='Foreign-currency reverse-charge VAT requires a separately qualified NOK tax base.'

def equal(actual,expected):assert round(float(actual or 0),2)==expected,(actual,expected)
def rejected(action,message=MESSAGE):
    frappe.db.savepoint('fx_guard_rejection')
    try:action()
    except frappe.ValidationError as error:
        assert message in str(error),str(error)
        frappe.db.rollback(save_point='fx_guard_rejection')
    else:raise AssertionError('Unsupported foreign reverse-charge flow was accepted')

try:
    company=frappe.get_doc('Company','Runtime Reverse Services')
    accounts={row.account_number:row.name for row in frappe.get_all('Account',
        filters={'company':company.name},fields=['name','account_number'])}
    supplier=frappe.get_all('Supplier',pluck='name')[0]
    category=frappe.get_doc({'doctype':'Tax Category','title':'Runtime native FX qualification'}).insert()
    frappe.set_user('runtime-vat-owner@example.invalid')
    assert 'System Manager' not in frappe.get_roles()
    def invoice(kind='On Net Total',amount=0,**extra):
        return frappe.get_doc({'doctype':'Purchase Invoice','company':company.name,
            'supplier':supplier,'posting_date':'2026-09-16','set_posting_time':1,
            'bill_date':'2026-09-16','bill_no':'SYNTHETIC-FX-QUALIFICATION',
            'due_date':'2026-10-31','currency':'EUR','conversion_rate':10,
            'disable_rounded_total':1,'tax_category':category.name,
            'items':[{'item_code':'RUNTIME-VAT-SERVICE','qty':1,'rate':100,
                'expense_account':accounts['4500'],'cost_center':company.cost_center,CODE:'86'}],
            'taxes':[{'charge_type':kind,'account_head':accounts[number],
                'rate':25 if kind=='On Net Total' else 0,'tax_amount':amount,
                'category':'Total','add_deduct_tax':direction,
                'description':'Synthetic native FX probe','cost_center':company.cost_center}
                for number,direction in [('2704','Deduct'),('2714','Add')]],**extra})

    for kind,amount,expected in [('On Net Total',0,250),('Actual',27.5,275),('Actual',27.53425,275.3)]:
        doc=invoice(kind,amount)
        # This calls the real core calculator, not the app's validation event.
        # It proves why native configuration alone cannot qualify a different FX base.
        doc.set_missing_values();doc.calculate_taxes_and_totals()
        equal(doc.base_grand_total,1000)
        equal(doc.taxes[0].base_tax_amount,expected)
        equal(doc.taxes[1].base_tax_amount,expected)
        detail=next(row for row in doc._item_wise_tax_details if row.tax is doc.taxes[0])
        equal(detail.taxable_amount,-1000)
        assert doc.taxes[0].precision('tax_amount')==2
        rejected(doc.insert)
    print('PASS native EUR calculator: net rows give 1000 base / 250 VAT; fixed amounts give 275 or 275.30 VAT but retain 1000 base; ordinary saves reject unsupported reverse FX')

    # Credit notes against a qualified NOK original must not open a foreign path.
    from erpnext.controllers.sales_and_purchase_return import make_return_doc
    original=frappe.get_all('Purchase Invoice',filters={'company':company.name,
        'docstatus':1,'is_return':0},pluck='name')[0]
    credit=make_return_doc('Purchase Invoice',original)
    credit.currency='EUR';credit.conversion_rate=10
    for row in credit.items:row.qty=-1
    rejected(credit.insert,'Exchange Rate must be same as')
    credit=make_return_doc('Purchase Invoice',original)
    credit.currency='EUR'  # Core's original numeric rate alone is not a NOK base.
    for row in credit.items:row.qty=-1
    rejected(credit.insert)

    order=frappe.get_doc({'doctype':'Purchase Order','company':company.name,
        'supplier':supplier,'transaction_date':'2026-09-16','schedule_date':'2026-09-20',
        'currency':'EUR','conversion_rate':10,'disable_rounded_total':1,
        'tax_category':category.name,
        'items':[{'item_code':'RUNTIME-VAT-SERVICE','qty':1,'rate':100,
            'schedule_date':'2026-09-20','cost_center':company.cost_center,CODE:'86'}],
        'taxes':[row.as_dict() for row in invoice().taxes]})
    rejected(order.insert)
    print('PASS ordinary owner native manual-header foreign purchase order and changed-currency credit remain blocked')

    # Neither ordinary foreign-currency purchase nor the qualified NOK reverse
    # flow should be blocked. Use real inserts/submissions and native GL/report.
    domestic=invoice(taxes=[{'charge_type':'On Net Total','account_head':accounts['2710'],
        'rate':25,'category':'Total','add_deduct_tax':'Add','description':'Synthetic native VAT',
        'cost_center':company.cost_center}])
    domestic.items[0].set(CODE,'1');domestic.insert();domestic.submit()
    row=next(row for row in collect({'company':company.name,'from_date':'2026-09-01',
        'to_date':'2026-09-30'}) if row['voucher']==domestic.name)
    equal(row['base_amount'],1000);equal(row['input_vat'],250);equal(row['output_vat'],0)
    native_nok=invoice(currency='NOK',conversion_rate=1);native_nok.insert();native_nok.submit()
    row=next(row for row in collect({'company':company.name,'from_date':'2026-09-01',
        'to_date':'2026-09-30'}) if row['voucher']==native_nok.name)
    equal(row['base_amount'],100);equal(row['input_vat'],25);equal(row['output_vat'],25)
    print('PASS native ordinary EUR purchase and qualified NOK reverse invoice still submit and reconcile with the VAT report')
finally:
    frappe.db.rollback();frappe.destroy()
