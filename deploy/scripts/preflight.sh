#!/usr/bin/env bash
set -Eeuo pipefail

release_dir="${1:?release directory is required}"
root="${SOLAR_AI_ROOT:-/opt/solar-ai}"
host_env="${root}/config/host.env"
secret_env="${root}/secrets/ai.env"
deploy_env="${release_dir}/deploy.env"
compose_file="${release_dir}/docker-compose.prod.yml"

fail() {
  printf 'PRECHECK FAILED: %s\n' "$*" >&2
  exit 1
}

for command in docker awk cosign curl dig grep sed sort stat df ip tr tail; do
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
acme_email="$(env_value ACME_EMAIL)"
monitoring_bind_ip="$(env_value AI_MONITORING_BIND_IP)"

[[ "${public_domain}" =~ ^[a-z0-9][a-z0-9.-]*[a-z0-9]$ ]] \
  && [[ "${public_domain}" == *.* ]] \
  || fail "AI_PUBLIC_DOMAIN must be a lower-case fully-qualified domain name"
[[ "${dns_zone}" =~ ^[a-z0-9][a-z0-9.-]*[a-z0-9]$ ]] \
  && [[ "${public_domain}" == *."${dns_zone}" ]] \
  || fail "AI_DNS_ZONE must be the authoritative parent zone of AI_PUBLIC_DOMAIN"
[[ "${public_ipv4}" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]] \
  || fail "AI_PUBLIC_IPV4 is missing or malformed"
[[ "${acme_email}" =~ ^[^[:space:]@]+@[^[:space:]@]+\.[^[:space:]@]+$ ]] \
  || fail "ACME_EMAIL is missing or malformed"
test -n "${monitoring_bind_ip}" \
  || fail "AI_MONITORING_BIND_IP is missing from ${host_env}"

"${release_dir}/deploy/scripts/verify-public-ip.sh" "${public_ipv4}" \
  || fail "AI_PUBLIC_IPV4 ${public_ipv4} is neither a local address nor the active DigitalOcean Reserved IPv4"
ip address show | grep -Fq "${monitoring_bind_ip}" \
  || fail "AI_MONITORING_BIND_IP ${monitoring_bind_ip} is not configured on this VPS"

# Check the authoritative servers, not only a potentially stale recursive DNS
# cache. Every authoritative answer must point to this VPS, otherwise clients
# can intermittently reach the wrong host and ACME issuance is unsafe to start.
mapfile -t nameservers < <(dig +short NS "${dns_zone}" | sed 's/\.$//' | sort -u)
(( ${#nameservers[@]} > 0 )) \
  || fail "no authoritative nameserver was found for ${dns_zone}"
for nameserver in "${nameservers[@]}"; do
  mapfile -t authoritative_ipv4 < <(
    dig +short "@${nameserver}" A "${public_domain}" \
      | awk '/^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$/' \
      | sort -u
  )
  (( ${#authoritative_ipv4[@]} == 1 )) \
    && [ "${authoritative_ipv4[0]}" = "${public_ipv4}" ] \
    || fail "${nameserver} does not resolve ${public_domain} exclusively to ${public_ipv4}"
done

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
  "${root}/data/classification-feedback" \
  "${root}/data/alloy" \
  "${root}/data/caddy/data" \
  "${root}/data/caddy/config"; do
  test -d "${path}" || fail "missing persistent directory ${path}"
  test -w "${path}" || fail "persistent directory is not writable: ${path}"
done

if ! grep -Eq '^(DEEPSEEK_API_KEY|GEMINI_API_KEY|ANTHROPIC_API_KEY)=.+$' "${secret_env}"; then
  fail "at least one non-empty LLM provider key is required"
fi

docker compose \
  --project-name solar-ai \
  --env-file "${host_env}" \
  --env-file "${deploy_env}" \
  -f "${compose_file}" \
  config --quiet

printf 'AI production preflight passed for %s\n' "${image_ref}"
