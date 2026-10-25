// Existing receipt fields, source references and native Norwegian report.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
(async()=>{
 const base=process.env.ERP_LANGUAGE_TEST_URL;assert.match(base||'',/^http:\/\/127\.0\.0\.1:\d+$/);
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 try {
  const context=await browser.newContext({baseURL:base,viewport:{width:1440,height:1080}});
  assert.equal((await context.request.post('/api/method/login',{form:{usr:'runtime-vat-owner@example.invalid',pwd:'Synthetic-vat-owner-only-2026!'}})).status(),200);
  async function record(doctype,filters,fields){
   const response=await context.request.get(`/api/resource/${encodeURIComponent(doctype)}?filters=${encodeURIComponent(JSON.stringify(filters))}&fields=${encodeURIComponent(JSON.stringify(fields))}`);
   assert.equal(response.status(),200);return (await response.json()).data[0];
  }
  const source=await record('Purchase Invoice',{company:'Runtime Import Flow',docstatus:1,currency:'NOK'},['supplier']);
  const output=await record('Account',{company:'Runtime Import Flow',account_number:'2705'},['name']);
  const page=await context.newPage();page.setDefaultTimeout(60000);
  const errors=[];page.on('pageerror',error=>errors.push(error.message));
  await page.goto('/desk/purchase-receipt/new-purchase-receipt');
  await page.waitForFunction(()=>window.cur_frm?.doctype==='Purchase Receipt'&&cur_frm.fields_dict?.items&&!frappe.request.ajax_count);
  await page.evaluate(async supplier=>{await cur_frm.set_value('company','Runtime Import Flow');await cur_frm.set_value('supplier',supplier);},source.supplier);
  await page.waitForFunction(()=>!cur_frm.updating_party_details&&!frappe.request.ajax_count&&cur_frm.doc.currency==='NOK');
  await page.evaluate(async()=>{
   await cur_frm.set_value('set_posting_time',1);await cur_frm.set_value('posting_date','2026-09-25');
   const row=cur_frm.doc.items.find(row=>!row.item_code)||frappe.model.add_child(cur_frm.doc,'Purchase Receipt Item','items');
   await frappe.model.set_value(row.doctype,row.name,'item_code','RUNTIME-IMPORT-NONSTOCK');
  });
  await page.waitForFunction(()=>!frappe.request.ajax_count&&cur_frm.doc.items[0]?.uom);
  await page.evaluate(async()=>{const row=cur_frm.doc.items[0];await frappe.model.set_value(row.doctype,row.name,'qty',1);await frappe.model.set_value(row.doctype,row.name,'rate',1000);});
  await page.waitForFunction(()=>!frappe.request.ajax_count&&!cur_frm.__norway_vat_preview);
  await page.evaluate(()=>{const row=cur_frm.doc.items[0];return frappe.model.set_value(row.doctype,row.name,'item_tax_template','Vareimport – deklarasjon uten beregning av MVA - IMF');});
  await page.waitForFunction(()=>!frappe.request.ajax_count&&!cur_frm.__norway_vat_preview&&cur_frm.doc.items[0]?.custom_norway_vat_code==='85'&&cur_frm.doc.grand_total===1000);
  await page.evaluate(()=>cur_frm.fields_dict.items.grid.grid_rows[0].toggle_view(true));
  for (const label of ['Deklarasjonsgrunnlag (NOK)','Ekspedisjonsdato','Deklarasjonsreferanse']) await page.getByText(label,{exact:true}).first().waitFor({state:'visible'});
  await page.evaluate(async()=>{
   const row=cur_frm.doc.items[0];await frappe.model.set_value(row.doctype,row.name,'custom_norway_vat_base',1200);
   await frappe.model.set_value(row.doctype,row.name,'custom_norway_import_date','2026-09-20');
   await frappe.model.set_value(row.doctype,row.name,'custom_norway_customs_reference','SYNTHETIC-BROWSER-IMPORT-'+Date.now());
  });
  await page.waitForFunction(()=>!frappe.request.ajax_count&&!cur_frm.__norway_vat_preview);
  await page.evaluate(()=>cur_frm.fields_dict.items.grid.grid_rows[0].toggle_view(false));
  await page.getByRole('button',{name:/^Lagre/}).first().click();
  await page.waitForFunction(()=>!cur_frm.doc.__islocal&&!frappe.request.ajax_count);
  assert.deepEqual(await page.evaluate(()=>({base:cur_frm.doc.items[0].custom_norway_vat_base,date:cur_frm.doc.items[0].custom_norway_import_date,total:cur_frm.doc.grand_total,code:cur_frm.doc.items[0].custom_norway_vat_code})),{base:1200,date:'2026-09-20',total:1000,code:'85'});
  await page.goto('/desk/journal-entry/new-journal-entry');
  await page.waitForFunction(()=>window.cur_frm?.doctype==='Journal Entry'&&cur_frm.fields_dict?.accounts&&!frappe.request.ajax_count);
  await page.evaluate(async account=>{
   await cur_frm.set_value('company','Runtime Import Flow');
   const row=cur_frm.doc.accounts[0]||frappe.model.add_child(cur_frm.doc,'Journal Entry Account','accounts');
   await frappe.model.set_value(row.doctype,row.name,'account',account);
   await frappe.model.set_value(row.doctype,row.name,'custom_norway_vat_code','81');
  },output.name);
  await page.waitForFunction(()=>!frappe.request.ajax_count);
  await page.locator('[role="tab"][data-fieldname="more_info_tab"]').click();
  await page.evaluate(()=>{const section=cur_frm.fields_dict.reference;if(section.is_collapsed())section.head.click();});
  await page.getByText('Ekspedisjonsdato',{exact:true}).first().waitFor({state:'visible'});
  await page.getByText('Deklarasjonsreferanse',{exact:true}).first().waitFor({state:'visible'});
  await page.evaluate(()=>{const row=cur_frm.doc.accounts[0];return frappe.model.set_value(row.doctype,row.name,'custom_norway_vat_code','86');});
  await page.getByText('Fakturadato',{exact:true}).first().waitFor({state:'visible'});
  await page.goto('/desk/query-report/Norsk%20MVA-spesifikasjon?company=Runtime%20Import%20Flow&from_date=2026-09-01&to_date=2026-09-30&return_type=Ordinary%20VAT%20return');
  await page.waitForFunction(()=>window.frappe?.query_report?.report_name==='Norsk MVA-spesifikasjon'&&frappe.query_report.data?.some(row=>row.vat_code==='85')&&!frappe.request.ajax_count);
  const data=await page.evaluate(()=>frappe.query_report.data);
  assert.equal(data.find(row=>row.vat_code==='81').base_amount,5000);assert.equal(data.find(row=>row.vat_code==='81').output_vat,1250);assert.equal(data.find(row=>row.vat_code==='81').input_vat,750);
  assert.equal(data.find(row=>row.vat_code==='85').base_amount,1300);assert.equal(data.find(row=>row.vat_code==='85').vat_rate,0);
  assert.deepEqual(errors,[]);
  console.log('PASS owner native Norwegian zero-import receipt fields/draft, customs labels on existing journal reference fields and September5000/1250/750 plus1300 zero-import report without draft duplication');
 } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exit(1);});
