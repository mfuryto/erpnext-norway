#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "$0")/.." && pwd)
fixture=$(mktemp -d)
project="erpnext-runtime-ci-$$"
export ERP_RUNTIME_PROJECT="$project"
compose=(docker compose --env-file "$fixture/deploy/.env" -p "$project" -f "$fixture/compose.yaml")
cleanup() {
  if [[ -f "$fixture/deploy/.env" ]]; then
    # Only this script's newly created, synthetic project is removed.
    "${compose[@]}" down --timeout 15 -v --remove-orphans >/dev/null 2>&1 || true
  fi
  if [[ -d "$fixture/data" ]]; then
    docker run --rm --user 0 --entrypoint sh -v "$fixture/data:/fixture-data" \
      frappe/erpnext:v16.51.1@sha256:a856e7f65c7bfc9cfa2e74f95b62e11d37190c380d958cbf3bea5d05e2ec9268 \
      -c "chown -R $(id -u):$(id -g) /fixture-data" >/dev/null 2>&1 || true
  fi
  rm -rf "$fixture"
}
trap cleanup EXIT
cp "$root/compose.yaml" "$fixture/compose.yaml"
cp -a "$root/scripts" "$root/deploy" "$fixture/"
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
"${compose[@]}" run --rm --no-deps -T backend bench --site accounting backup \
  --with-files --ignore-backup-conf \
  --backup-path-db /home/frappe/frappe-bench/sites/accounting/private/backups/runtime-ci.sql.gz \
  --backup-path-files /home/frappe/frappe-bench/sites/accounting/private/backups/runtime-ci-public.tar \
  --backup-path-private-files /home/frappe/frappe-bench/sites/accounting/private/backups/runtime-ci-private.tar \
  --backup-path-conf /home/frappe/frappe-bench/sites/accounting/private/backups/runtime-ci-config.json
runtime_python damage
"${compose[@]}" run --rm --no-deps -T create-site bash -euc '
  cd /home/frappe/frappe-bench
  backup_dir="$PWD/sites/accounting/private/backups"
  cp "$backup_dir/runtime-ci-config.json" sites/accounting/site_config.json
  bench --site accounting restore "$backup_dir/runtime-ci.sql.gz" \
    --db-root-username root --db-root-password "$DB_ROOT_PASSWORD" \
    --with-public-files "$backup_dir/runtime-ci-public.tar" \
    --with-private-files "$backup_dir/runtime-ci-private.tar"
  bench --site accounting migrate
'
runtime_python verify
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
