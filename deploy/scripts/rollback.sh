#!/usr/bin/env bash
set -Eeuo pipefail

root="${SOLAR_AI_ROOT:-/opt/solar-ai}"
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
target="${1:-}"
if [ -z "${target}" ]; then
  target="$(readlink -f "${root}/previous")"
fi
target="$(readlink -f "${target}")"

test -d "${target}" || {
  printf 'rollback target does not exist: %s\n' "${target}" >&2
  exit 1
}
[[ "${target}" =~ ^${root}/releases/[0-9a-f]{40}$ ]] || {
  printf 'rollback target must be an immutable release under %s/releases: %s\n' \
    "${root}" "${target}" >&2
  exit 1
}
test -r "${target}/deploy.env" || {
  printf 'rollback deploy.env is missing: %s\n' "${target}" >&2
  exit 1
}

image_ref="$(sed -n 's/^AI_IMAGE=//p' "${target}/deploy.env" | tail -n 1)"
[[ "${image_ref}" =~ @sha256:[0-9a-f]{64}$ ]] || {
  printf 'rollback image is not pinned by sha256: %s\n' "${image_ref}" >&2
  exit 1
}
export AI_IMAGE="${image_ref}"

# Run the hardened preflight that ships with this rollback implementation,
# while validating and deploying the immutable target release payload.
"${script_dir}/preflight.sh" "${target}"

host_env="${root}/config/host.env"
docker compose \
  --project-name solar-ai \
  --env-file "${host_env}" \
  --env-file "${target}/deploy.env" \
  -f "${target}/docker-compose.prod.yml" \
  pull
docker compose \
  --project-name solar-ai \
  --env-file "${host_env}" \
  --env-file "${target}/deploy.env" \
  -f "${target}/docker-compose.prod.yml" \
  up -d --remove-orphans --wait --wait-timeout 240
docker exec solar-ai-module python /app/deploy/scripts/verify-models.py
docker exec solar-ai-module python /app/deploy/scripts/smoke-test.py

public_domain="$(sed -n 's/^AI_PUBLIC_DOMAIN=//p' "${host_env}" | tail -n 1 | tr -d '\r')"
tls_smoke_attempts=0
until docker exec \
  -e "AI_SMOKE_REST_URL=https://${public_domain}" \
  -e "AI_SMOKE_GRPC_TARGET=${public_domain}:443" \
  -e AI_SMOKE_GRPC_TLS=true \
  -e "AI_SMOKE_GRPC_AUTHORITY=${public_domain}" \
  solar-ai-module python /app/deploy/scripts/smoke-test.py; do
  tls_smoke_attempts=$((tls_smoke_attempts + 1))
  if (( tls_smoke_attempts >= 24 )); then
    docker logs --tail 200 solar-ai-caddy >&2 || true
    printf 'TLS ingress smoke failed after %d attempts\n' "${tls_smoke_attempts}" >&2
    exit 1
  fi
  sleep 5
done

# The immediately previous immutable release may predate Alloy's private
# metrics port. Do not make emergency rollback impossible for that one legacy
# revision; still verify node/cAdvisor plus the end-to-end Loki marker.
require_alloy_metrics=true
if ! grep -Fq ':12345:12345' "${target}/docker-compose.prod.yml"; then
  require_alloy_metrics=false
fi
"${script_dir}/verify-observability.sh" \
  "${host_env}" "rollback-$(basename "${target}")" "${require_alloy_metrics}"

old_current=""
if [ -L "${root}/current" ]; then
  old_current="$(readlink -f "${root}/current")"
fi
ln -sfn "${target}" "${root}/current"
if [ -n "${old_current}" ] && [ "${old_current}" != "${target}" ]; then
  ln -sfn "${old_current}" "${root}/previous"
fi

printf 'AI production rolled back to %s\n' "${target}"
