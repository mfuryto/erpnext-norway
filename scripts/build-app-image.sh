#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
image_file=$(mktemp)
trap 'rm -f -- "$image_file"' EXIT
docker build --file deploy/Dockerfile.app --progress plain \
  --label "org.opencontainers.image.revision=$(git rev-parse HEAD)" \
  --iidfile "$image_file" . >&2
docker image inspect --format '{{.Id}}' "$(cat "$image_file")"
