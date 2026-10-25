// Native item tax selector, immutable classification and report category/period.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
(async()=>{
 const base=process.env.ERP_LANGUAGE_TEST_URL;assert.match(base||'',/^http:\/\/127\.0\.0\.1:\d+$/);
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 try {
  const context=await browser.newContext({baseURL:base,viewport:{width:1440,height:1080}});
  const login=await context.request.post('/api/method/login',{form:{usr:'runtime-vat-owner@example.invalid',pwd:'Synthetic-vat-owner-only-2026!'}});assert.equal(login.status(),200);
  const filters=encodeURIComponent(JSON.stringify({company:'Runtime Quarterly Services',docstatus:1,is_return:0,currency:'NOK'}));
  const response=await context.request.get(`/api/resource/Purchase%20Invoice?filters=${filters}&fields=${encodeURIComponent(JSON.stringify(['supplier']))}`);
  const supplier=(await response.json()).data[0].supplier;
  const page=await context.newPage();page.setDefaultTimeout(60000);
  const errors=[];page.on('pageerror',error=>errors.push(error.message));
  await page.goto('/desk/purchase-invoice/new-purchase-invoice');
  await page.waitForFunction(()=>window.cur_frm?.doctype==='Purchase Invoice'&&cur_frm.fields_dict?.items&&!frappe.request.ajax_count);
  await page.evaluate(async supplier=>{await cur_frm.set_value('company','Runtime Quarterly Services');await cur_frm.set_value('supplier',supplier);},supplier);
  await page.waitForFunction(()=>!cur_frm.updating_party_details&&!frappe.request.ajax_count&&cur_frm.doc.currency==='NOK');
  await page.evaluate(async()=>{
   await cur_frm.set_value('set_posting_time',1);await cur_frm.set_value('posting_date','2026-06-20');await cur_frm.set_value('bill_date','2026-06-20');await cur_frm.set_value('bill_no','SYNTHETIC-QUARTER-BROWSER-'+Date.now());await cur_frm.set_value('due_date','2026-10-31');
   const row=cur_frm.doc.items.find(row=>!row.item_code)||frappe.model.add_child(cur_frm.doc,'Purchase Invoice Item','items');
   await frappe.model.set_value(row.doctype,row.name,'item_code','RUNTIME-VAT-SERVICE');
  });
  await page.waitForFunction(()=>!frappe.request.ajax_count&&cur_frm.doc.items[0]?.uom);
  await page.evaluate(async()=>{const row=cur_frm.doc.items[0];await frappe.model.set_value(row.doctype,row.name,'qty',1);await frappe.model.set_value(row.doctype,row.name,'rate',1000);});
  await page.waitForFunction(()=>!frappe.request.ajax_count&&!cur_frm.__norway_vat_preview);
  await page.evaluate(()=>{const row=cur_frm.doc.items[0];return frappe.model.set_value(row.doctype,row.name,'item_tax_template','Tjenestekjøp fra utlandet – kvartalsgrunnlag før MVA-registrering - QVS');});
  await page.waitForFunction(()=>!frappe.request.ajax_count&&!cur_frm.__norway_vat_preview&&cur_frm.doc.items[0]?.custom_norway_quarterly_service===1&&cur_frm.doc.grand_total===1000);
  await page.evaluate(()=>cur_frm.fields_dict.items.grid.grid_rows[0].toggle_view(true));
  await page.getByText('Tjenestekjøp fra utlandet før MVA-registrering',{exact:true}).first().waitFor({state:'visible'});
  const meta=await page.evaluate(()=>frappe.meta.get_docfield('Purchase Invoice Item','custom_norway_quarterly_service',cur_frm.doc.name).read_only);assert.equal(meta,1);
  await page.evaluate(()=>cur_frm.fields_dict.items.grid.grid_rows[0].toggle_view(false));
  await page.getByRole('button',{name:/^Lagre/}).first().click();
  await page.waitForFunction(()=>!cur_frm.doc.__islocal&&!frappe.request.ajax_count);
  const saved=await page.evaluate(()=>({basis:cur_frm.doc.items[0].custom_norway_quarterly_service,deduction:cur_frm.doc.items[0].custom_norway_deduction_percent,total:cur_frm.doc.grand_total,type:cur_frm.doc.custom_norway_vat_return_type}));
  assert.deepEqual(saved,{basis:1,deduction:0,total:1000,type:'Reverse-charge quarterly return'});
  const scope=encodeURIComponent('Reverse-charge quarterly return');
  await page.goto(`/desk/query-report/Norsk%20MVA-spesifikasjon?company=Runtime%20Quarterly%20Services&from_date=2026-04-01&to_date=2026-06-30&return_type=${scope}`);
  await page.waitForFunction(()=>window.frappe?.query_report?.report_name==='Norsk MVA-spesifikasjon'&&frappe.query_report.data?.some(row=>row.vat_code==='87')&&!frappe.request.ajax_count);
  const report=await page.evaluate(()=>({type:frappe.query_report.get_filter_value('return_type'),from:frappe.query_report.get_filter_value('from_date'),to:frappe.query_report.get_filter_value('to_date'),row:frappe.query_report.data.find(row=>row.vat_code==='87'),label:frappe.query_report.get_filter('return_type').$input.find('option:selected').text()}));
  assert.equal(report.type,'Reverse-charge quarterly return');assert.equal(report.from,'2026-04-01');assert.equal(report.to,'2026-06-30');assert.equal(report.row.base_amount,2050.02);assert.equal(report.row.output_vat,512.5);assert.match(report.label,/Kvartalsmelding/);
  assert.deepEqual(errors,[]);
  console.log('PASS native Norwegian quarterly item template/classification, unchanged1000 payable, zero input deduction, draft persistence and native report category/period512.50 VAT');
 } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exit(1);});
