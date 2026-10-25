FROM frappe/erpnext:v16.52.1@sha256:eb1c22d2bb926ed97352b63334507bf0297f1ca1244b406e3f30869ca5d0092b
USER frappe
COPY --chown=frappe:frappe deploy/app-build-requirements.txt /tmp/app-build-requirements.txt
RUN uv pip install --python env/bin/python --require-hashes --no-deps -r /tmp/app-build-requirements.txt
COPY --chown=frappe:frappe apps/erpnext_norway /home/frappe/frappe-bench/apps/erpnext_norway
RUN uv pip install --python env/bin/python --no-deps --no-build-isolation -e apps/erpnext_norway \
    && ln -s /home/frappe/frappe-bench/apps/erpnext_norway/erpnext_norway/chart_data/norway.json \
    apps/erpnext/erpnext/accounts/doctype/account/chart_of_accounts/verified/no_erpnext_norway.json \
    && env/bin/python -c "from frappe.bundler import link_assets_dir; link_assets_dir('/home/frappe/frappe-bench/apps/erpnext_norway/erpnext_norway/public', '/home/frappe/frappe-bench/assets/erpnext_norway')"
LABEL org.opencontainers.image.title="ERPNext Norway" \
      org.opencontainers.image.version="0.4.17" \
      no.erpnext-norway.base="v16.52.1"
