#!/usr/bin/env bash
set -Eeuo pipefail

host_env="${1:-${SOLAR_AI_ROOT:-/opt/solar-ai}/config/host.env}"
release_id="${2:-manual}"
require_alloy_metrics="${3:-true}"

case "${require_alloy_metrics}" in
  true|false) ;;
  *)
    printf 'require_alloy_metrics must be true or false\n' >&2
    exit 2
    ;;
esac

env_value() {
  local key="${1:?environment key is required}"
  sed -n "s/^${key}=//p" "${host_env}" | tail -n 1 | tr -d '\r'
}

monitoring_bind_ip="$(env_value AI_MONITORING_BIND_IP)"
platform_wireguard_ipv4="$(env_value PLATFORM_WIREGUARD_IPV4)"
public_domain="$(env_value AI_PUBLIC_DOMAIN)"
loki_push_url="$(env_value LOKI_PUSH_URL)"
loki_base_url="${loki_push_url%/loki/api/v1/push}"

for metrics_url in \
  "http://${monitoring_bind_ip}:9100/metrics" \
  "http://${monitoring_bind_ip}:8082/metrics"; do
  curl --fail --silent --show-error --max-time 10 \
    "${metrics_url}" >/dev/null || {
      printf 'private AI metrics endpoint failed: %s\n' "${metrics_url}" >&2
      exit 1
    }
done
if [[ "${require_alloy_metrics}" == true ]]; then
  curl --fail --silent --show-error --max-time 10 \
    "http://${monitoring_bind_ip}:12345/metrics" >/dev/null || {
      printf 'private Alloy metrics endpoint failed: %s:12345/metrics\n' \
        "${monitoring_bind_ip}" >&2
      exit 1
    }
fi
curl --fail --silent --show-error --max-time 10 \
  "http://${platform_wireguard_ipv4}:3100/ready" >/dev/null

# Prove the complete log path, not only Alloy process health: create a unique
# Caddy access log, then query that exact marker back from backend Loki through
# WireGuard. This closes the common gap where Alloy is Ready but cannot push.
observability_marker="ai-${release_id}-$(date +%s)"
docker exec \
  -e "AI_OBSERVABILITY_URL=https://${public_domain}/ready?marker=${observability_marker}" \
  solar-ai-module python -c \
  'import os, urllib.request; urllib.request.urlopen(os.environ["AI_OBSERVABILITY_URL"], timeout=10).read()'

loki_query="{container=\"solar-ai-caddy\"} |= \"${observability_marker}\""
log_attempts=0
until curl --fail --silent --show-error --get \
  --data-urlencode "query=${loki_query}" \
  --data-urlencode 'limit=10' \
  --data-urlencode 'direction=backward' \
  "${loki_base_url}/loki/api/v1/query_range" |
  jq -e '.data.result | length > 0' >/dev/null; do
  log_attempts=$((log_attempts + 1))
  if (( log_attempts >= 12 )); then
    docker logs --tail 200 solar-ai-alloy >&2 || true
    printf 'AI log marker did not arrive in backend Loki over WireGuard\n' >&2
    exit 1
  fi
  sleep 5
done

printf 'AI observability verified: exporters=up alloy_metrics=%s loki_marker=%s\n' \
  "${require_alloy_metrics}" "${observability_marker}"
