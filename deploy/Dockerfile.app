FROM frappe/erpnext:v16.51.1@sha256:a856e7f65c7bfc9cfa2e74f95b62e11d37190c380d958cbf3bea5d05e2ec9268
USER frappe
COPY --chown=frappe:frappe deploy/app-build-requirements.txt /tmp/app-build-requirements.txt
RUN uv pip install --python env/bin/python --require-hashes --no-deps -r /tmp/app-build-requirements.txt
COPY --chown=frappe:frappe apps/erpnext_norway /home/frappe/frappe-bench/apps/erpnext_norway
RUN uv pip install --python env/bin/python --no-deps --no-build-isolation -e apps/erpnext_norway \
    && ln -s /home/frappe/frappe-bench/apps/erpnext_norway/erpnext_norway/chart_data/norway.json \
    apps/erpnext/erpnext/accounts/doctype/account/chart_of_accounts/verified/no_erpnext_norway.json
LABEL org.opencontainers.image.title="ERPNext Norway" \
      org.opencontainers.image.version="0.4.3" \
      no.erpnext-norway.base="v16.51.1"
