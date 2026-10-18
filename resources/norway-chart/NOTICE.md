# Source and licence

The account codes and Norwegian names are derived from Odoo's official `l10n_no`
dataset at commit `2ff84495182bc2d6e87b616731f865677a12b213`:

- `addons/l10n_no/data/template/account.account-no.csv`
- Module author: Rolv Råen; manifest also credits Bringsvor Consulting AS.
- Odoo contributors; copyright and licence notices are preserved under `upstream/`.
- Upstream module manifest: LGPL-3. Original LGPLv3/GPLv3 text is included unchanged.

All 745 codes and Norwegian names are preserved. `source.json` records the exact
revision and hashes. `norway.csv` is a modified representation for ERPNext's native
Chart of Accounts Importer and retains the dataset's LGPLv3 terms. The converter
itself follows this repository's GPLv3 licence. No Odoo executable code is installed.

Native account groups and ERPNext-specific account types are adapter configuration,
not a direct import of Odoo's account semantics. In particular, 2740 is Tax rather
than Payable, 1570 is not a cash/bank account, and financial income in 80xx is placed
under Income. Payroll and tax-result accounts being present do not imply support
for payroll, AS annual accounts or personal income tax.

This is an established software account dataset, not a reproduced proprietary
NS 4102 publication or a claim of Standard Norge certification. Norwegian VAT
rules, SAF-T mapping and tax-year qualifications are separate work.
