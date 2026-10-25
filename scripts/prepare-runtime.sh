#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
[[ -f deploy/.env ]] || { echo 'Run scripts/init-runtime.py first.' >&2; exit 1; }
compose=(docker compose --env-file deploy/.env -p "${ERP_RUNTIME_PROJECT:-erpnext-norway}" -f compose.yaml)
"${compose[@]}" config --quiet
"${compose[@]}" --profile setup pull
# Only ERPNext's new directories are created. Existing database/site files are retained.
mkdir -p data/{database,sites,logs,redis-queue}
# The official application user is uid/gid 1000. MariaDB/Redis initialise their own paths.
docker run --rm --user 0 --entrypoint sh \
  -v "$PWD/data/sites:/sites" -v "$PWD/data/logs:/logs" \
  frappe/erpnext:v16.52.1@sha256:eb1c22d2bb926ed97352b63334507bf0297f1ca1244b406e3f30869ca5d0092b \
  -c 'chown 1000:1000 /sites /logs'
"${compose[@]}" up -d --wait --wait-timeout 180 db redis-cache redis-queue
"${compose[@]}" run --rm --no-deps configurator
"${compose[@]}" run --rm --no-deps create-site
"${compose[@]}" up -d --wait --wait-timeout 300
"${compose[@]}" exec -T backend bench --site accounting list-apps
printf 'ERPNext runtime ready. Norwegian localisation is not installed.\n'
