#!/usr/bin/env bash
set -Eeuo pipefail

release_sha="${1:?full Git SHA is required}"
image_ref="${2:?immutable image reference is required}"
root="${SOLAR_AI_ROOT:-/opt/solar-ai}"
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
payload_dir="$(cd -- "${script_dir}/../.." && pwd)"

[[ "${release_sha}" =~ ^[0-9a-f]{40}$ ]] || {
  printf 'release SHA must contain exactly 40 lowercase hex characters\n' >&2
  exit 2
}
[[ "${image_ref}" =~ @sha256:[0-9a-f]{64}$ ]] || {
  printf 'image must be pinned by sha256 digest\n' >&2
  exit 2
}
# Shell variables have higher Compose precedence than --env-file. Force the
# verified argument so an inherited/stale AI_IMAGE can never override deploy.env.
export AI_IMAGE="${image_ref}"

umask 027
mkdir -p "${root}/releases" "${root}/config" "${root}/secrets" "${root}/data"
release_dir="${root}/releases/${release_sha}"
if [ -e "${release_dir}" ]; then
  existing_ref="$(sed -n 's/^AI_IMAGE=//p' "${release_dir}/deploy.env" 2>/dev/null | tail -n 1)"
  [ "${existing_ref}" = "${image_ref}" ] || {
    printf 'immutable release directory already exists with another image: %s\n' "${release_dir}" >&2
    exit 1
  }
else
  mkdir -p "${release_dir}"
  cp -a "${payload_dir}/docker-compose.prod.yml" "${release_dir}/"
  cp -a "${payload_dir}/deploy" "${release_dir}/deploy"
  printf 'AI_IMAGE=%s\n' "${image_ref}" > "${release_dir}/deploy.env"
  chmod 0640 "${release_dir}/deploy.env"
fi

host_env="${root}/config/host.env"
compose() {
  docker compose \
    --project-name solar-ai \
    --env-file "${host_env}" \
    --env-file "${release_dir}/deploy.env" \
    -f "${release_dir}/docker-compose.prod.yml" \
    "$@"
}

previous_release=""
if [ -L "${root}/current" ]; then
  previous_release="$(readlink -f "${root}/current")"
fi

rollback_on_failure() {
  status=$?
  if (( status == 0 )); then
    return
  fi
  printf 'Deployment failed; attempting rollback to %s\n' "${previous_release:-none}" >&2
  if [ -n "${previous_release}" ] && [ -d "${previous_release}" ]; then
    # Use the rollback implementation shipped with the candidate release so
    # fixes to rollback/preflight logic also protect the immediately previous
    # release. The target Compose payload and image remain immutable.
    "${release_dir}/deploy/scripts/rollback.sh" "${previous_release}" || true
  else
    compose down --remove-orphans || true
  fi
  exit "${status}"
}

# Neither preflight nor image pulling mutates the running Compose project. Arm
# rollback only immediately before `compose up`, where production state can
# actually begin to change.
"${release_dir}/deploy/scripts/preflight.sh" "${release_dir}"
compose pull
trap rollback_on_failure EXIT
compose up -d --remove-orphans --wait --wait-timeout 240
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

"${release_dir}/deploy/scripts/verify-observability.sh" \
  "${host_env}" "${release_sha:0:12}"

if [ -n "${previous_release}" ] && [ "${previous_release}" != "${release_dir}" ]; then
  ln -sfn "${previous_release}" "${root}/previous"
fi
ln -sfn "${release_dir}" "${root}/current"

trap - EXIT
printf 'AI production deployed: sha=%s image=%s\n' "${release_sha}" "${image_ref}"
