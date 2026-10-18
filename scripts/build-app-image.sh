#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
image_file=$(mktemp)
trap 'rm -f -- "$image_file"' EXIT
docker build --file deploy/Dockerfile.app --progress plain \
  --label "org.opencontainers.image.revision=$(git rev-parse HEAD)" \
  --iidfile "$image_file" . >&2
app_image=$(docker image inspect --format '{{.Id}}' "$(cat "$image_file")")
# Keep each built version addressable when normal dangling-image cleanup runs.
docker tag "$app_image" "erpnext-norway:sha256-${app_image#sha256:}"
printf '%s\n' "$app_image"
