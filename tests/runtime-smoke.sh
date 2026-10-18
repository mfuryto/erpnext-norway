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
    "${compose[@]}" down -v --remove-orphans >/dev/null 2>&1 || true
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
import json,sys,urllib.request
port=sys.argv[1]
with urllib.request.urlopen(f'http://127.0.0.1:{port}/api/method/ping') as r:
    assert json.load(r)['message']=='pong'
with urllib.request.urlopen(f'http://127.0.0.1:{port}/socket.io/?EIO=4&transport=polling') as r:
    assert r.read().startswith(b'0{')
print('PASS native site, HTTP endpoint and Socket.IO polling')
PY
key_hash() {
  "${compose[@]}" exec -T backend env/bin/python -c 'import hashlib,json; key=json.load(open("sites/accounting/site_config.json"))["encryption_key"]; assert key; print(hashlib.sha256(key.encode()).hexdigest())'
}
initial_key_hash=$(key_hash)
"${compose[@]}" restart backend frontend
"${compose[@]}" up -d --wait --wait-timeout 300
[[ "$(key_hash)" == "$initial_key_hash" ]]
printf 'PASS restart preserves site encryption key and storage\n'
