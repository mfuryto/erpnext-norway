"""Export actual foreign-service VAT details already fixed in NOK by core."""
import hashlib
import json
import os
from pathlib import Path
import sys
from decimal import Decimal
from lxml import etree
import frappe
os.chdir('/home/frappe/frappe-bench/sites')
frappe.init(site='accounting',sites_path='/home/frappe/frappe-bench/sites')
frappe.connect();frappe.set_user('Administrator');frappe.conf.host_name='http://frontend:8080'
from erpnext_norway import saft, saft_builder as xml
C='Runtime Currency Services';OWNER='runtime-vat-owner@example.invalid';NS={'s':xml.NS}


def configure():
    c=frappe.get_doc('Company',C);c.phone_no='90000000';c.save()
    maps={'1920':('balanseverdiForOmloepsmiddel','1920'),'2400':('kortsiktigGjeld','2400'),
        '4500':('varekostnad','4500'),'2704':('kortsiktigGjeld','2740'),
        '2714':('kortsiktigGjeld','2740'),'2709':('kortsiktigGjeld','2740'),
        '2718':('kortsiktigGjeld','2740'),'7740':('annenDriftskostnad','7700'),
        '8160':('finanskostnad','8160')}
    for r in frappe.get_all('Account',filters={'company':C,'is_group':0},fields=['name','account_number','account_type']):
        key=r.account_number or ('2400' if r.account_type=='Payable' else '')
        if key not in maps:continue
        account=frappe.get_doc('Account',r.name)
        if not account.get(saft.MAPPING):
            category,code=maps[key];account.append(saft.MAPPING,{'year':2026,'category':category,'code':code});account.save()


def export():
    content=saft.build(C,'2026-01-01','2026-12-31');xml.validate_saf_t(content)
    return content,etree.fromstring(content)


def infos(root,name):
    return root.xpath('.//s:Line[s:SourceDocumentID="'+name+'"]/s:TaxInformation',namespaces=NS)


def check(root):
    evidence=json.loads(frappe.db.get_default('runtime_currency_evidence'))
    bills=[r for r in evidence['documents'] if r['doctype']=='Purchase Invoice']
    for r in bills[:6]:
        doc=frappe.get_doc(r['doctype'],r['name']);percent=doc.items[0].custom_norway_deduction_percent
        info=infos(root,doc.name);assert len(info)==1,(doc.name,len(info))
        i=info[0];base=Decimal('550.68' if doc.is_return else '1101.37')
        assert Decimal(i.xpath('string(s:TaxBase)',namespaces=NS))==base
        net={100:Decimal(0),60:Decimal('55.07' if doc.is_return else '110.13'),0:Decimal('137.67' if doc.is_return else '275.34')}[percent]
        side='DebitTaxAmount' if (doc.is_return and net) or (not doc.is_return and not net) else 'CreditTaxAmount'
        assert Decimal(i.xpath('string(s:'+side+'/s:Amount)',namespaces=NS))==net
        assert i.xpath('string(s:TaxCode)',namespaces=NS)==('86' if percent else '87')
        if not doc.is_return and percent==60:
            # The stored tax basis is neither the EUR amount nor accounting cost.
            expense=root.xpath('.//s:Line[s:SourceDocumentID="'+doc.name+'" and s:AccountID="4500"]/s:DebitAmount/s:Amount/text()',namespaces=NS)
            assert expense==['1110.14'],expense
    order_bill=frappe.get_doc('Purchase Invoice',bills[6]['name'])
    assert sorted(Decimal(i.xpath('string(s:TaxBase)',namespaces=NS)) for i in infos(root,order_bill.name))==[Decimal(495),Decimal(540)]
    native=frappe.get_all('GL Entry',filters={'company':C},fields=['name','debit','credit'])
    assert set(root.xpath('.//s:Line/s:RecordID/text()',namespaces=NS))=={r.name for r in native}
    assert Decimal(root.xpath('string(.//s:TotalDebit)',namespaces=NS))==sum((xml._money(r.debit) for r in native),Decimal())
    assert Decimal(root.xpath('string(.//s:TotalCredit)',namespaces=NS))==sum((xml._money(r.credit) for r in native),Decimal())
    assert root.xpath('.//s:Line/*[s:CurrencyCode="EUR"]/s:CurrencyAmount',namespaces=NS)
    assert not root.xpath('.//s:TaxInformation/s:DebitNOKTaxAmount|.//s:TaxInformation/s:CreditNOKTaxAmount',namespaces=NS)


def low_rate():
    from erpnext.controllers.sales_and_purchase_return import make_return_doc
    evidence=json.loads(frappe.db.get_default('runtime_currency_evidence'))
    original=frappe.get_doc('Purchase Invoice',evidence['documents'][0]['name'])
    frappe.db.savepoint('saft_currency_low')
    for percent,net in [(100,'0.00'),(60,'52.86'),(0,'132.16')]:
        bill=frappe.copy_doc(original);bill.bill_no='SYNTHETIC-SAFT-LOW-'+str(percent)
        bill.set('taxes',[])
        bill.items[0].item_tax_template='Tjenestekjøp fra utlandet – MVA 12 % – 100 % fradrag - FCV'
        bill.items[0].custom_norway_deduction_percent=percent
        bill.insert();bill.submit()
        _,root=export();info=infos(root,bill.name)
        assert len(info)==1
        assert info[0].xpath('string(s:TaxCode)',namespaces=NS)==('88' if percent else '89')
        assert Decimal(info[0].xpath('string(s:TaxBase)',namespaces=NS))==Decimal('1101.37')
        side='DebitTaxAmount' if percent==100 else 'CreditTaxAmount'
        assert Decimal(info[0].xpath('string(s:'+side+'/s:Amount)',namespaces=NS))==Decimal(net)
        if percent==60:
            credit=make_return_doc('Purchase Invoice',bill.name)
            credit.posting_date=credit.bill_date='2026-10-16';credit.set_posting_time=1
            credit.bill_no='SYNTHETIC-SAFT-LOW-CREDIT';credit.items[0].qty=-1
            credit.insert();credit.submit()
            _,root=export();info=infos(root,credit.name)
            assert len(info)==1
            assert Decimal(info[0].xpath('string(s:DebitTaxAmount/s:Amount)',namespaces=NS))==Decimal('26.43')
            credit.cancel()
            _,root=export();info=infos(root,credit.name)
            assert len(info)==2
            assert sorted(i.xpath('string(s:DebitTaxAmount/s:Amount)',namespaces=NS) or i.xpath('string(s:CreditTaxAmount/s:Amount)',namespaces=NS) for i in info)==['26.43','26.43']
    frappe.db.rollback(save_point='saft_currency_low')
    print('PASS actual EUR low12 codes88/89 full/partial/zero, half-credit and retained cancellation')


try:
    if sys.argv[1]=='seed':configure()
    frappe.set_user(OWNER);assert 'System Manager' not in frappe.get_roles()
    content,root=export();check(root);low_rate()
    if sys.argv[1]=='seed':
        from frappe.utils.file_manager import save_file
        proof=save_file('synthetic-saft-currency.xml',content,'Company',C,is_private=1)
        frappe.db.set_default('runtime_saft_currency',json.dumps({'file':proof.name,'sha256':hashlib.sha256(content).hexdigest()}));frappe.db.commit()
    else:
        proof=json.loads(frappe.db.get_default('runtime_saft_currency'))
        file=frappe.get_doc('File',proof['file']);assert file.is_private
        assert hashlib.sha256(Path(file.get_full_path()).read_bytes()).hexdigest()==proof['sha256']
    print('PASS SAF-T currency '+sys.argv[1]+': native NOK basis1101.37/550.68, deduction100/60/0 net0/110.13/275.34, order bases495/540, native EUR/payment/FX/rounding GL and private XML')
finally:
    frappe.db.rollback();frappe.destroy()
