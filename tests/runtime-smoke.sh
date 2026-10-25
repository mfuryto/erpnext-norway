#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "$0")/.." && pwd)
fixture=$(mktemp -d)
project="erpnext-runtime-ci-$$"
export ERP_RUNTIME_PROJECT="$project"
compose=(docker compose --env-file "$fixture/deploy/.env" -p "$project" -f "$fixture/compose.yaml")
cleanup() {
  test_exit=$?
  if [[ "$test_exit" != 0 && "${ERP_RUNTIME_KEEP_ON_FAILURE:-0}" == 1 ]]; then
    printf 'Synthetic fixture retained for debugging: %s (project %s)\n' "$fixture" "$project"
    return
  fi
  if [[ "$test_exit" != 0 && -f "$fixture/backups/runtime-ci/runtime.log" ]]; then
    failure_log=$(mktemp /tmp/erpnext-runtime-failure.XXXXXX)
    cp "$fixture/backups/runtime-ci/runtime.log" "$failure_log"
    printf 'Private runtime failure log retained at %s\n' "$failure_log"
  fi
  if [[ -f "$fixture/deploy/.env" ]]; then
    # Only this script's newly created, synthetic project is removed.
    "${compose[@]}" down --timeout 15 -v --remove-orphans >/dev/null 2>&1 || true
  fi
  if [[ -d "$fixture/data" ]]; then
    docker run --rm --user 0 --entrypoint sh -v "$fixture/data:/fixture-data" \
      frappe/erpnext:v16.52.1@sha256:eb1c22d2bb926ed97352b63334507bf0297f1ca1244b406e3f30869ca5d0092b \
      -c "chown -R $(id -u):$(id -g) /fixture-data" >/dev/null 2>&1 || true
  fi
  rm -rf "$fixture"
}
trap cleanup EXIT
cp "$root/compose.yaml" "$fixture/compose.yaml"
cp -a "$root/scripts" "$root/deploy" "$fixture/"
cp "$root/resources/norway-chart/norway.csv" "$fixture/deploy/norway.csv"
rm -f "$fixture/deploy/.env"
port=$(python3 - <<'PY'
import socket
with socket.socket() as s:
    s.bind(('127.0.0.1',0))
    print(s.getsockname()[1])
PY
)
python3 "$fixture/scripts/init-runtime.py" --url http://accounting.invalid --port "$port"
bash "$fixture/scripts/prepare-runtime.sh"
python3 - "$port" <<'PY'
import base64,hashlib,json,socket,sys,urllib.request
port=sys.argv[1]
with urllib.request.urlopen(f'http://127.0.0.1:{port}/api/method/ping') as r:
    assert json.load(r)['message']=='pong'
with urllib.request.urlopen(f'http://127.0.0.1:{port}/socket.io/?EIO=4&transport=polling') as r:
    assert r.read().startswith(b'0{')
print('PASS native site, HTTP endpoint and Socket.IO polling')
key = base64.b64encode(b'runtime-ci-check').decode()
request = (
    'GET /socket.io/?EIO=4&transport=websocket HTTP/1.1\r\n'
    f'Host: 127.0.0.1:{port}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n'
    f'Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n'
)
with socket.create_connection(('127.0.0.1', int(port)), timeout=15) as s:
    s.sendall(request.encode())
    response = b''
    while b'\r\n\r\n' not in response:
        chunk = s.recv(4096)
        assert chunk, 'WebSocket closed before Upgrade response'
        response += chunk
        assert len(response) < 65536
headers = response.split(b'\r\n\r\n', 1)[0].decode()
assert headers.split('\r\n')[0].split()[1] == '101', headers
values = {name.lower(): value.strip() for name, value in
          (line.split(':', 1) for line in headers.split('\r\n')[1:] if ':' in line)}
expected = base64.b64encode(hashlib.sha1((key + '258EAFA5-E914-47DA-95CA-C5AB0DC85B11').encode()).digest()).decode()
assert values['sec-websocket-accept'] == expected
print('PASS Socket.IO WebSocket Upgrade through Compose frontend (not external proxy)')
PY
key_hash() {
  "${compose[@]}" exec -T backend env/bin/python -c 'import hashlib,json; key=json.load(open("sites/accounting/site_config.json"))["encryption_key"]; assert key; print(hashlib.sha256(key.encode()).hexdigest())'
}
initial_key_hash=$(key_hash)
"${compose[@]}" restart backend frontend
"${compose[@]}" up -d --wait --wait-timeout 300
[[ "$(key_hash)" == "$initial_key_hash" ]]
printf 'PASS restart preserves site encryption key and storage\n'

if [[ "${ERP_TEST_APP:-0}" == 1 ]]; then
  app_image=$(bash "$root/scripts/build-app-image.sh")
  python3 "$root/scripts/update-runtime.py" --root "$fixture" --image "$app_image" --name before-app
  "${compose[@]}" run --rm --no-deps -T backend env/bin/python - fresh < "$root/tests/runtime-app.py"
fi

# Destructive recovery is confined to the fresh synthetic fixture above.
# Stop all writers and HTTP access; use one-off commands for backup and restore.
"${compose[@]}" stop --timeout 15 frontend backend websocket scheduler queue-long queue-short
runtime_python() {
  "${compose[@]}" run --rm --no-deps -T backend env/bin/python - "$1" \
    < "$root/tests/runtime-recovery.py"
}
"${compose[@]}" run --rm --no-deps -T create-site env/bin/python - \
  < "$root/tests/runtime-module-visibility.py"
runtime_python seed
if [[ "${ERP_TEST_APP:-0}" == 1 ]]; then
  "${compose[@]}" up -d --no-deps --wait --wait-timeout 300 backend websocket frontend
  "${compose[@]}" run --rm --no-deps -T create-site env/bin/python - < "$root/tests/runtime-company-chart.py"
fi
"${compose[@]}" run --rm --no-deps -T create-site env/bin/python - \
  < "$root/tests/runtime-core-accounting.py"
if [[ "${ERP_TEST_APP:-0}" == 1 ]]; then
  "${compose[@]}" run --rm --no-deps -T backend env/bin/python - probe < "$root/tests/runtime-app.py"
  "${compose[@]}" run --rm --no-deps -T backend env/bin/python - seed < "$root/tests/runtime-language.py"
  "${compose[@]}" run --rm --no-deps -T backend env/bin/python - < "$root/tests/runtime-ui-language.py"
  "${compose[@]}" run --rm --no-deps -T backend env/bin/python - < "$root/tests/runtime-language-surfaces.py"
  "${compose[@]}" run --rm --no-deps -T backend env/bin/python - seed < "$root/tests/runtime-vat.py"
  "${compose[@]}" run --rm --no-deps -T backend env/bin/python - < "$root/tests/runtime-vat-treatment.py"
  "${compose[@]}" run --rm --no-deps -T backend env/bin/python - < "$root/tests/runtime-vat-charges.py"
  "${compose[@]}" run --rm --no-deps -T backend env/bin/python - < "$root/tests/runtime-vat-return-rates.py"
  "${compose[@]}" run --rm --no-deps -T backend env/bin/python - seed < "$root/tests/runtime-vat-valuation.py"
  "${compose[@]}" run --rm --no-deps -T backend env/bin/python - < "$root/tests/runtime-vat-valuation-race.py"
  "${compose[@]}" run --rm --no-deps -T backend env/bin/python - seed < "$root/tests/runtime-vat-freight.py"
  "${compose[@]}" run --rm --no-deps -T backend env/bin/python - seed < "$root/tests/runtime-vat-reverse.py"
  "${compose[@]}" run --rm --no-deps -T backend env/bin/python - < "$root/tests/runtime-vat-threshold-core.py"
  "${compose[@]}" run --rm --no-deps -T backend env/bin/python - < "$root/tests/runtime-vat-fx-core.py"
  "${compose[@]}" run --rm --no-deps -T backend env/bin/python - seed < "$root/tests/runtime-vat-journal-reversal.py"
  "${compose[@]}" run --rm --no-deps -T backend env/bin/python - seed < "$root/tests/runtime-vat-sales-chain.py"
  "${compose[@]}" run --rm --no-deps -T backend env/bin/python - seed < "$root/tests/runtime-vat-currency.py"
  "${compose[@]}" run --rm --no-deps -T backend env/bin/python - seed < "$root/tests/runtime-vat-quarterly.py"
  "${compose[@]}" run --rm --no-deps -T backend env/bin/python - seed < "$root/tests/runtime-vat-quarterly-race.py"
  "${compose[@]}" run --rm --no-deps -T backend env/bin/python - seed < "$root/tests/runtime-vat-import-journal.py"
  "${compose[@]}" run --rm --no-deps -T backend env/bin/python - seed < "$root/tests/runtime-vat-import-flow.py"
  "${compose[@]}" run --rm --no-deps -T backend env/bin/python - seed < "$root/tests/runtime-vat-export.py"
  "${compose[@]}" run --rm --no-deps -T backend env/bin/python - < "$root/tests/runtime-vat-portal-cycle.py"
  "${compose[@]}" run --rm --no-deps -T backend env/bin/python - seed < "$root/tests/runtime-vat-evidence.py"
  "${compose[@]}" run --rm --no-deps -T backend env/bin/python - < "$root/tests/runtime-vat-settlement-race.py"
else
  "${compose[@]}" run --rm --no-deps -T create-site env/bin/python - \
    < "$root/tests/runtime-native-controls.py"
fi
"${compose[@]}" up -d --wait --wait-timeout 300
if [[ "${ERP_TEST_BROWSER:-0}" == 1 ]]; then
  ERP_LANGUAGE_TEST_URL="http://127.0.0.1:$port" node "$root/tests/runtime-language-browser.cjs"
  ERP_LANGUAGE_TEST_URL="http://127.0.0.1:$port" node "$root/tests/runtime-vat-browser.cjs"
  ERP_LANGUAGE_TEST_URL="http://127.0.0.1:$port" node "$root/tests/runtime-vat-treatment-browser.cjs"
  ERP_LANGUAGE_TEST_URL="http://127.0.0.1:$port" node "$root/tests/runtime-vat-reverse-browser.cjs"
  ERP_LANGUAGE_TEST_URL="http://127.0.0.1:$port" node "$root/tests/runtime-vat-currency-browser.cjs"
  ERP_LANGUAGE_TEST_URL="http://127.0.0.1:$port" node "$root/tests/runtime-vat-quarterly-browser.cjs"
  ERP_LANGUAGE_TEST_URL="http://127.0.0.1:$port" node "$root/tests/runtime-vat-import-browser.cjs"
  ERP_LANGUAGE_TEST_URL="http://127.0.0.1:$port" node "$root/tests/runtime-vat-sales-browser.cjs"
  ERP_LANGUAGE_TEST_URL="http://127.0.0.1:$port" node "$root/tests/runtime-vat-valuation-browser.cjs"
  ERP_LANGUAGE_TEST_URL="http://127.0.0.1:$port" node "$root/tests/runtime-vat-freight-browser.cjs"
  "${compose[@]}" run --rm --no-deps -T backend env/bin/python - desktop < "$root/tests/runtime-language-surfaces.py"
  ERP_LANGUAGE_TEST_URL="http://127.0.0.1:$port" node "$root/tests/runtime-language-surfaces-browser.cjs"
  "${compose[@]}" run --rm --no-deps -T backend env/bin/python - restore-desktop < "$root/tests/runtime-language-surfaces.py"
fi
if [[ "${ERP_TEST_APP:-0}" == 1 ]]; then
  "${compose[@]}" run --rm --no-deps -T backend env/bin/python - < "$root/tests/runtime-vat-return-sources.py"
  if [[ "${ERP_TEST_BROWSER:-0}" == 1 ]]; then
    ERP_LANGUAGE_TEST_URL="http://127.0.0.1:$port" node "$root/tests/runtime-vat-return-sources-browser.cjs"
  fi
  "${compose[@]}" run --rm --no-deps -T backend env/bin/python - finish < "$root/tests/runtime-vat-return-sources.py"
  "${compose[@]}" run --rm --no-deps -T backend env/bin/python - snapshot < "$root/tests/runtime-app.py"
fi
python3 "$fixture/scripts/backup-runtime.py" --name runtime-ci
(cd "$fixture/backups/runtime-ci" && sha256sum --check SHA256SUMS)
[[ "$(stat -c %a "$fixture/backups/runtime-ci/runtime.env")" == 600 ]]
cmp "$fixture/deploy/.env" "$fixture/backups/runtime-ci/runtime.env"
"${compose[@]}" stop --timeout 15 frontend backend websocket scheduler queue-long queue-short
runtime_python damage
# Recover from the exported private bundle, not the surviving source backup.
"${compose[@]}" run --rm --no-deps -T backend env/bin/python -c \
  "import shutil; shutil.rmtree('sites/accounting/private/runtime-backups/runtime-ci')"
backend_container=$("${compose[@]}" ps --all --quiet backend)
docker cp "$fixture/backups/runtime-ci/native/." \
  "$backend_container:/home/frappe/frappe-bench/sites/accounting/private/runtime-backups/restored-ci"
"${compose[@]}" run --rm --no-deps -T --user 0 backend chown -R 1000:1000 \
  /home/frappe/frappe-bench/sites/accounting/private/runtime-backups/restored-ci
"${compose[@]}" run --rm --no-deps -T create-site bash -euc '
  cd /home/frappe/frappe-bench
  backup_dir="$PWD/sites/accounting/private/runtime-backups/restored-ci"
  cp "$backup_dir/site_config.before.json" sites/accounting/site_config.json
  bench --site accounting restore "$backup_dir/database.sql.gz" \
    --db-root-username root --db-root-password "$DB_ROOT_PASSWORD" \
    --with-public-files "$backup_dir/public.tar" \
    --with-private-files "$backup_dir/private.tar"
  bench --site accounting migrate
'
runtime_python verify
if [[ "${ERP_TEST_APP:-0}" == 1 ]]; then
  "${compose[@]}" run --rm --no-deps -T backend env/bin/python - verify < "$root/tests/runtime-app.py"
  "${compose[@]}" run --rm --no-deps -T backend env/bin/python - verify < "$root/tests/runtime-language.py"
  "${compose[@]}" run --rm --no-deps -T backend env/bin/python - verify < "$root/tests/runtime-vat.py"
  "${compose[@]}" run --rm --no-deps -T backend env/bin/python - verify < "$root/tests/runtime-vat-reverse.py"
  "${compose[@]}" run --rm --no-deps -T backend env/bin/python - verify < "$root/tests/runtime-vat-journal-reversal.py"
  "${compose[@]}" run --rm --no-deps -T backend env/bin/python - verify < "$root/tests/runtime-vat-sales-chain.py"
  "${compose[@]}" run --rm --no-deps -T backend env/bin/python - verify < "$root/tests/runtime-vat-currency.py"
  "${compose[@]}" run --rm --no-deps -T backend env/bin/python - verify < "$root/tests/runtime-vat-quarterly.py"
  "${compose[@]}" run --rm --no-deps -T backend env/bin/python - verify < "$root/tests/runtime-vat-quarterly-race.py"
  "${compose[@]}" run --rm --no-deps -T backend env/bin/python - verify < "$root/tests/runtime-vat-import-journal.py"
  "${compose[@]}" run --rm --no-deps -T backend env/bin/python - verify < "$root/tests/runtime-vat-import-flow.py"
  "${compose[@]}" run --rm --no-deps -T backend env/bin/python - verify < "$root/tests/runtime-vat-export.py"
  "${compose[@]}" run --rm --no-deps -T backend env/bin/python - verify < "$root/tests/runtime-vat-valuation.py"
  "${compose[@]}" run --rm --no-deps -T backend env/bin/python - verify < "$root/tests/runtime-vat-freight.py"
  "${compose[@]}" run --rm --no-deps -T backend env/bin/python - verify < "$root/tests/runtime-vat-evidence.py"
fi
"${compose[@]}" up -d --wait --wait-timeout 300
[[ "$(key_hash)" == "$initial_key_hash" ]]
"${compose[@]}" exec -T frontend curl --fail --silent --show-error --max-time 10 \
  http://127.0.0.1:8080/api/method/ping
printf '\nPASS HTTP after backup/restore and migration\n'
python3 - "$port" <<'PY'
import sys,urllib.error,urllib.request
base = f'http://127.0.0.1:{sys.argv[1]}'
with urllib.request.urlopen(base + '/files/runtime-ci.txt', timeout=15) as response:
    assert response.read() == b'synthetic recovery evidence'
try:
    urllib.request.urlopen(base + '/private/files/runtime-ci.txt', timeout=15)
except urllib.error.HTTPError as error:
    assert error.code == 403, f'Expected guest denial, got HTTP {error.code}'
else:
    raise AssertionError('Restored private file was accessible to guest')
print('PASS restored public file served and private file denied to guest')
PY
