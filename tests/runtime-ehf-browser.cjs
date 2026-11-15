// Use the native invoice fields and private Attach download, without a new workspace.
const {chromium}=require('playwright');const assert=require('node:assert/strict');
(async()=>{
 const base=process.env.ERP_LANGUAGE_TEST_URL;assert.match(base||'',/^http:\/\/127\.0\.0\.1:\d+$/);
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 try{
  const context=await browser.newContext({baseURL:base,viewport:{width:1440,height:1080}});
  assert.equal((await context.request.post('/api/method/login',{form:{usr:'runtime-ehf@example.invalid',pwd:'Synthetic-ehf-owner-only-2026!'}})).status(),200);
  const response=await context.request.get('/api/resource/Sales%20Invoice?filters='+encodeURIComponent(JSON.stringify({company:'Runtime EHF Example',docstatus:1,custom_norway_invoice_delivery:'EHF'})));
  assert.equal(response.status(),200);const name=(await response.json()).data[0].name;
  const page=await context.newPage();page.setDefaultTimeout(60000);const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('/desk/sales-invoice/'+encodeURIComponent(name));
  await page.waitForFunction(()=>window.cur_frm?.doctype==='Sales Invoice'&&cur_frm.doc.custom_norway_ehf_xml&&!frappe.request.ajax_count);
  const fields=await page.evaluate(()=>({system:frappe.user_roles.includes('System Manager'),
   channel:__(cur_frm.fields_dict.custom_norway_invoice_delivery.df.label),reference:__(cur_frm.fields_dict.custom_norway_ehf_buyer_reference.df.label),
   xml:__(cur_frm.fields_dict.custom_norway_ehf_xml.df.label),readonly:cur_frm.fields_dict.custom_norway_ehf_xml.df.read_only,
   url:cur_frm.doc.custom_norway_ehf_xml}));
  assert.equal(fields.system,false);assert.equal(fields.channel,'Leveringsmåte for faktura');assert.equal(fields.reference,'EHF-mottakerreferanse');
  assert.equal(fields.xml,'EHF-fil');assert.equal(fields.readonly,1);
  await page.getByText('EHF-fil er klargjort. Levering er ikke bekreftet.',{exact:true}).waitFor();
  const xml=await context.request.get(fields.url);assert.equal(xml.status(),200);assert.match(await xml.text(),/<(?:Invoice|CreditNote)\b/);
  const guest=await browser.newContext({baseURL:base});assert.equal((await guest.request.get(fields.url)).status(),403);await guest.close();
  assert.deepEqual(errors,[]);await page.screenshot({path:'/tmp/erpnext-ehf-nb.png',fullPage:true});
  console.log('PASS ordinary native NB invoice EHF fields, prepared status and private XML download; guest403');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
