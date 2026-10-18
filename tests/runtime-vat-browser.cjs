// Native Company registration fields and tax selection; synthetic localhost only.
const {chromium} = require('playwright');
const fs = require('node:fs/promises');
const assert = require('node:assert/strict');
(async () => {
  const base = process.env.ERP_LANGUAGE_TEST_URL;
  assert.match(base || '', /^http:\/\/127\.0\.0\.1:\d+$/);
  const output = process.env.ERP_LANGUAGE_TEST_OUTPUT || '/tmp/erpnext-language-browser';
  await fs.mkdir(output, {recursive: true});
  const browser = await chromium.launch({headless: true, args: ['--no-sandbox']});
  try {
    const context = await browser.newContext({baseURL: base, viewport: {width: 1440, height: 1080}});
    const response = await context.request.post('/api/method/login', {form: {
      usr: 'runtime-vat-owner@example.invalid', pwd: 'Synthetic-vat-owner-only-2026!'
    }});
    assert.equal(response.status(), 200);
    const page = await context.newPage();
    await page.goto('/app/company/Runtime%20VAT%20Example');
    await page.waitForFunction(() => window.cur_frm?.doc?.name === 'Runtime VAT Example');
    const registration = await page.evaluate(() => ({
      status: cur_frm.doc.custom_norway_vat_status, date: cur_frm.doc.custom_norway_vat_from,
      label: __('Norwegian VAT registration', null, 'Company'),
      shown: cur_frm.fields_dict.custom_norway_vat_status.$input.find(':selected').text(),
      dateLabel: cur_frm.fields_dict.custom_norway_vat_from.$wrapper.find('label').first().clone().children().remove().end().text().trim(),
      systemManager: frappe.user_roles.includes('System Manager')
    }));
    assert.deepEqual(registration, {status: 'Registered', date: '2026-10-15',
      label: 'MVA-registrering (Norge)', shown: 'Registrert', dateLabel: 'MVA-registrert fra', systemManager: false});
    await page.screenshot({path: `${output}/vat-company-registration-nb.png`, fullPage: true});
    const fields = encodeURIComponent(JSON.stringify(['name', 'customer', 'company_tax_id', 'grand_total', 'total_taxes_and_charges']));
    const filters = encodeURIComponent(JSON.stringify({company: 'Runtime VAT Example', docstatus: 1, is_return: 0}));
    const salesResponse = await context.request.get(`/api/resource/Sales%20Invoice?fields=${fields}&filters=${filters}`);
    const sales = (await salesResponse.json()).data;
    const taxed = sales.find(row => row.total_taxes_and_charges === 250);
    const untaxed = sales.find(row => row.total_taxes_and_charges === 0);
    assert(taxed && untaxed);
    assert.equal(taxed.company_tax_id, '999999999 MVA');
    assert.equal(untaxed.company_tax_id, '999999999');
    for (const row of [untaxed, taxed]) {
      await page.goto(`/app/sales-invoice/${row.name}`);
      await page.waitForFunction(name => window.cur_frm?.doc?.name === name, row.name);
      const values = await page.evaluate(() => ({id: cur_frm.doc.company_tax_id, tax: cur_frm.doc.total_taxes_and_charges}));
      assert.equal(values.id, row.company_tax_id);
      assert.equal(values.tax, row.total_taxes_and_charges);
      await page.screenshot({path: `${output}/vat-${row.total_taxes_and_charges ? 'after' : 'before'}-invoice-nb.png`, fullPage: true});
    }
    await page.goto('/app/sales-invoice/new-sales-invoice-vat-audit');
    await page.waitForFunction(() => window.cur_frm?.doctype === 'Sales Invoice' && cur_frm.doc.__islocal);
    await page.evaluate(async customer => {
      await cur_frm.set_value('company', 'Runtime VAT Example');
      await cur_frm.set_value('customer', customer);
    }, taxed.customer);
    await page.waitForFunction(() => !cur_frm.updating_party_details && !frappe.request.ajax_count);
    await page.evaluate(() => cur_frm.set_value('posting_date', '2026-10-16'));
    await page.waitForFunction(() => !frappe.request.ajax_count);
    await page.evaluate(() => cur_frm.set_value('tax_category', 'Norge MVA 25 %'));
    await page.waitForFunction(() => cur_frm.doc.taxes_and_charges?.startsWith('Utgående MVA 25 %') && cur_frm.doc.taxes.length === 1);
    const choice = await page.evaluate(() => ({
      category: cur_frm.doc.tax_category, rate: cur_frm.doc.taxes[0].rate,
      account: cur_frm.doc.taxes[0].account_head, label: __('Tax Category', null, 'Sales Invoice')
    }));
    assert.equal(choice.category, 'Norge MVA 25 %');
    assert.equal(choice.rate, 25);
    assert(choice.account.startsWith('2700 '), choice.account);
    assert.equal(choice.label, 'Avgiftskategori');
    await page.screenshot({path: `${output}/vat-native-tax-selection-nb.png`, fullPage: true});
    console.log('PASS actual ordinary-owner Company registration, historical/current invoice snapshots and native 25% tax category selection');
  } finally {
    await browser.close();
  }
})().catch(error => {console.error(error); process.exit(1);});
