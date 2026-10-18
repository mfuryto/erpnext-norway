#!/usr/bin/env bash
set -euo pipefail
cd /home/frappe/frappe-bench
if [[ ! -f sites/accounting/site_config.json ]]; then
  # A partial install is deliberately not removed or overwritten automatically.
  [[ ! -d sites/accounting ]] || { echo 'Partial site found; inspect it before retrying.' >&2; exit 1; }
  bench new-site accounting --mariadb-user-host-login-scope='%' \
    --admin-password="$ADMIN_PASSWORD" --db-root-username=root \
    --db-root-password="$DB_ROOT_PASSWORD" --install-app erpnext --set-default
fi
bench --site accounting set-config host_name "$PUBLIC_URL"
bench --site accounting execute frappe.utils.password.get_encryption_key >/dev/null
bench --site accounting enable-scheduler
bench --site accounting list-apps
