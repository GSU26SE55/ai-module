#!/usr/bin/env bash
set -Eeuo pipefail

release_dir="${1:?release directory is required}"
root="${SOLAR_AI_ROOT:-/opt/solar-ai}"
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
host_env="${root}/config/host.env"
secret_env="${root}/secrets/ai.env"
deploy_env="${release_dir}/deploy.env"
compose_file="${release_dir}/docker-compose.prod.yml"

# The computed path is fixed relative to this signed deployment payload. The
# helper is also passed to ShellCheck independently by the Jenkins wildcard.
# shellcheck disable=SC1091
source "${script_dir}/network-functions.sh"

fail() {
  printf 'PRECHECK FAILED: %s\n' "$*" >&2
  exit 1
}

for command in docker awk caddy cosign curl dig grep sed sort stat df ip sleep systemctl tr tail jq; do
  command -v "${command}" >/dev/null 2>&1 || fail "missing command: ${command}"
done
docker info >/dev/null 2>&1 || fail "Docker daemon is unavailable"
docker compose version >/dev/null 2>&1 || fail "Docker Compose v2 is unavailable"

test -r "${host_env}" || fail "missing ${host_env}"
test -r "${secret_env}" || fail "missing ${secret_env}"
test -r "${deploy_env}" || fail "missing ${deploy_env}"
test -r "${compose_file}" || fail "missing ${compose_file}"

secret_mode="$(stat -c '%a' "${secret_env}")"
case "${secret_mode}" in
  600|640) ;;
  *) fail "${secret_env} must have mode 600 or 640, got ${secret_mode}" ;;
esac

image_ref="$(sed -n 's/^AI_IMAGE=//p' "${deploy_env}" | tail -n 1)"
[[ "${image_ref}" =~ @sha256:[0-9a-f]{64}$ ]] || fail "AI_IMAGE must use an immutable sha256 digest"

allowed_repository_file="${root}/config/allowed-image-repository"
cosign_public_key="${root}/config/cosign.pub"
test -r "${allowed_repository_file}" || fail "missing ${allowed_repository_file}"
test -r "${cosign_public_key}" || fail "missing ${cosign_public_key}"
allowed_repository="$(tr -d '[:space:]' < "${allowed_repository_file}")"
case "${image_ref}" in
  "${allowed_repository}"@sha256:*) ;;
  *) fail "image repository is not in the VPS allowlist" ;;
esac
cosign verify --key "${cosign_public_key}" "${image_ref}" >/dev/null

env_value() {
  local key="${1:?environment key is required}"
  sed -n "s/^${key}=//p" "${host_env}" | tail -n 1 | tr -d '\r'
}

public_domain="$(env_value AI_PUBLIC_DOMAIN)"
dns_zone="$(env_value AI_DNS_ZONE)"
public_ipv4="$(env_value AI_PUBLIC_IPV4)"
observability_mode="$(env_value AI_OBSERVABILITY_MODE)"
monitoring_bind_ip="$(env_value AI_MONITORING_BIND_IP)"
platform_wireguard_ipv4="$(env_value PLATFORM_WIREGUARD_IPV4)"
loki_push_url="$(env_value LOKI_PUSH_URL)"
docker_socket_gid="$(env_value AI_DOCKER_SOCKET_GID)"

if ! [[ "${public_domain}" =~ ^[a-z0-9][a-z0-9.-]*[a-z0-9]$ \
  && "${public_domain}" == *.* ]]; then
  fail "AI_PUBLIC_DOMAIN must be a lower-case fully-qualified domain name"
fi
if ! [[ "${dns_zone}" =~ ^[a-z0-9][a-z0-9.-]*[a-z0-9]$ \
  && "${public_domain}" == *."${dns_zone}" ]]; then
  fail "AI_DNS_ZONE must be the authoritative parent zone of AI_PUBLIC_DOMAIN"
fi
[[ "${public_ipv4}" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]] \
  || fail "AI_PUBLIC_IPV4 is missing or malformed"
case "${observability_mode}" in
  standalone) ;;
  central)
    [[ "${monitoring_bind_ip}" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]] \
      || fail "AI_MONITORING_BIND_IP is missing or malformed"
    [[ "${platform_wireguard_ipv4}" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]] \
      || fail "PLATFORM_WIREGUARD_IPV4 is missing or malformed"
    [[ "${monitoring_bind_ip}" != "${platform_wireguard_ipv4}" ]] \
      || fail "AI and platform WireGuard addresses must be different"
    [[ "${loki_push_url}" == "http://${platform_wireguard_ipv4}:3100/loki/api/v1/push" ]] \
      || fail "LOKI_PUSH_URL must use the platform WireGuard Loki bridge"
    [[ "${docker_socket_gid}" =~ ^[0-9]+$ ]] \
      || fail "AI_DOCKER_SOCKET_GID is missing or is not numeric"
    test -S /var/run/docker.sock \
      || fail "Docker socket /var/run/docker.sock does not exist"
    actual_docker_socket_gid="$(stat -c '%g' /var/run/docker.sock)"
    [[ "${docker_socket_gid}" = "${actual_docker_socket_gid}" ]] \
      || fail "AI_DOCKER_SOCKET_GID ${docker_socket_gid} does not match Docker socket GID ${actual_docker_socket_gid}"
    ;;
  *) fail "AI_OBSERVABILITY_MODE must be standalone or central" ;;
esac

# R3 runs one host-level Caddy for both Jenkins and AI. The Compose project is
# deliberately not allowed to own 80/443. Verify the installed site contract
# before pulling an image or mutating the running release.
host_caddyfile="/etc/caddy/Caddyfile"
test -r "${host_caddyfile}" || fail "host Caddyfile is not readable: ${host_caddyfile}"
systemctl is-active --quiet caddy || fail "host Caddy service is not active"
caddy validate --config "${host_caddyfile}" --adapter caddyfile >/dev/null \
  || fail "host Caddy configuration is invalid"
for expected_caddy_contract in \
  "${public_domain} {" \
  '@metrics path /metrics /metrics/*' \
  'respond "Forbidden" 403' \
  'reverse_proxy 127.0.0.1:18000' \
  'reverse_proxy @grpc h2c://127.0.0.1:15051'; do
  grep -Fq "${expected_caddy_contract}" "${host_caddyfile}" \
    || fail "host Caddy is missing AI contract: ${expected_caddy_contract}"
done
if [[ "${observability_mode}" == central ]]; then
  grep -Fq "remote_ip ${platform_wireguard_ipv4}" "${host_caddyfile}" \
    || fail "host Caddy does not allow the platform WireGuard peer to scrape metrics"
fi

# A 502/503 is valid before the first AI container starts; it still proves
# local TLS, certificate trust, SNI and the correct host virtual route.
caddy_probe_code="$(
  curl --silent --show-error --output /dev/null --write-out '%{http_code}' \
    --noproxy '*' \
    --connect-timeout 5 --max-time 10 \
    --resolve "${public_domain}:443:127.0.0.1" \
    "https://${public_domain}/ready"
)" || fail "host Caddy TLS/SNI probe failed for ${public_domain}"
case "${caddy_probe_code}" in
  200|502|503) ;;
  *) fail "host Caddy returned unexpected HTTP ${caddy_probe_code} for the AI route" ;;
esac

"${release_dir}/deploy/scripts/verify-public-ip.sh" "${public_ipv4}" \
  || fail "AI_PUBLIC_IPV4 ${public_ipv4} is neither a local address nor the active DigitalOcean Reserved IPv4"
if [[ "${observability_mode}" == central ]]; then
  ip -4 -o address show dev wg0 |
    awk '{print $4}' | cut -d/ -f1 | grep -Fxq "${monitoring_bind_ip}" \
    || fail "AI_MONITORING_BIND_IP ${monitoring_bind_ip} is not assigned to wg0"
  ip -4 route get "${platform_wireguard_ipv4}" |
    grep -Eq '(^|[[:space:]])dev wg0([[:space:]]|$)' \
    || fail "platform WireGuard address is not routed through wg0"

  # The deploy account intentionally has no CAP_NET_ADMIN, so it cannot query
  # handshake timestamps with `wg show`. The /32 route above plus this bounded
  # application-layer probe proves that the peer and encrypted path are usable.
  curl --fail --silent --show-error --connect-timeout 5 --max-time 10 \
    "http://${platform_wireguard_ipv4}:3100/ready" >/dev/null \
    || fail "Loki is not reachable through the platform WireGuard bridge"
fi

# Check the authoritative servers, not only a potentially stale recursive DNS
# cache. Every authoritative answer must point to this R3 host, otherwise
# clients can intermittently reach the wrong Jenkins/AI ingress.
dns_nameservers_for_zone "${dns_zone}" \
  || fail "no authoritative nameserver was found for ${dns_zone} after 5 attempts"
while IFS= read -r nameserver; do
  if ! authoritative_ipv4_matches \
    "${nameserver}" \
    "${public_domain}" \
    "${public_ipv4}"; then
    last_answers="${AUTHORITATIVE_IPV4_LAST_ANSWERS:-none}"
    fail "${nameserver} does not resolve ${public_domain} exclusively to ${public_ipv4} after 5 attempts (last answers: ${last_answers})"
  fi
done <<<"${DNS_NAMESERVER_LAST_ANSWERS}"

mapfile -t public_ipv6 < <(dig +short AAAA "${public_domain}" | awk '/:/')
(( ${#public_ipv6[@]} == 0 )) \
  || fail "remove stale AAAA records for ${public_domain} or explicitly add IPv6 support"

available_kb="$(df -Pk "${root}" | awk 'NR==2 {print $4}')"
(( available_kb >= 10 * 1024 * 1024 )) || fail "less than 10 GiB disk is available under ${root}"

available_mem_kb="$(awk '/MemAvailable:/ {print $2}' /proc/meminfo)"
(( available_mem_kb >= 2 * 1024 * 1024 )) || fail "less than 2 GiB RAM is currently available"

for path in \
  "${root}/data/kb" \
  "${root}/data/prescription-history" \
  "${root}/data/classification-feedback"; do
  test -d "${path}" || fail "missing persistent directory ${path}"
  test -w "${path}" || fail "persistent directory is not writable: ${path}"
done
if [[ "${observability_mode}" == central ]]; then
  test -d "${root}/data/alloy" \
    || fail "missing persistent directory ${root}/data/alloy"
  test -w "${root}/data/alloy" \
    || fail "persistent directory is not writable: ${root}/data/alloy"
fi

if ! grep -Eq '^(DEEPSEEK_API_KEY|GEMINI_API_KEY|ANTHROPIC_API_KEY)=.+$' "${secret_env}"; then
  fail "at least one non-empty LLM provider key is required"
fi

compose_profile_args=()
if [[ "${observability_mode}" == central ]]; then
  compose_profile_args+=(--profile central-observability)
fi
docker compose \
  --project-name solar-ai \
  --env-file "${host_env}" \
  --env-file "${deploy_env}" \
  "${compose_profile_args[@]}" \
  -f "${compose_file}" \
  config --quiet

printf 'AI production preflight passed for %s\n' "${image_ref}"
