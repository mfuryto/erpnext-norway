const {chromium}=require('playwright');
const assert=require('node:assert/strict');
(async()=>{
 const base=process.env.ERP_LANGUAGE_TEST_URL;
 assert.match(base||'',/^http:\/\/127\.0\.0\.1:\d+$/);
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 try {
  const context=await browser.newContext({baseURL:base});
  const login=await context.request.post('/api/method/login',{form:{usr:'runtime-owner@example.invalid',pwd:'Synthetic-owner-runtime-only-2026!'}});
  assert.equal(login.status(),200);
  const page=await context.newPage();page.setDefaultTimeout(60000);
  await page.goto('/desk/company/Runtime%20Norwegian%20Example');
  await page.waitForFunction(()=>window.cur_frm?.doctype==='Company'&&cur_frm.doc.name==='Runtime Norwegian Example'&&!frappe.request.ajax_count);
  await page.getByRole('button',{name:'Last ned SAF-T',exact:true}).click();
  await page.getByRole('dialog').getByText('Fra dato',{exact:true}).waitFor();
  await page.getByRole('dialog').getByText('Til dato',{exact:true}).waitFor();
  const query=new URLSearchParams({company:'Runtime Norwegian Example',from_date:'2026-01-01',to_date:'2026-12-31'});
  const url='/api/method/erpnext_norway.saft.download?'+query.toString();
  const response=await context.request.get(url);assert.equal(response.status(),200,await response.text());
  assert.match(response.headers()['content-disposition'],/attachment;.*SAF-T_Financial_/);
  const body=await response.text();assert.match(body,/<AuditFile/);assert.match(body,/<AuditFileVersion>1.40<\/AuditFileVersion>/);
  assert.match(body,/<TaxCode>0<\/TaxCode>/);
  const guest=await browser.newContext({baseURL:base});
  assert.equal((await guest.request.get(url)).status(),403);
  console.log('PASS ordinary owner Norwegian Company SAF-T button/date dialog, authenticated XML attachment and guest rejection');
 } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exit(1);});
