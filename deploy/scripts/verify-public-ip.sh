#!/usr/bin/env bash
set -Eeuo pipefail

expected_ipv4="${1:?expected public IPv4 is required}"
metadata_base="http://169.254.169.254/metadata/v1"

if ip -4 -o address show \
  | awk '{split($4, address, "/"); print address[1]}' \
  | grep -Fxq "${expected_ipv4}"; then
  printf 'Verified local public IPv4: %s\n' "${expected_ipv4}"
  exit 0
fi

# DigitalOcean Reserved IPv4 addresses are NATed to the Droplet anchor address
# and therefore do not appear in `ip address`. Trust only the link-local
# metadata service, require the assignment to be active, and require an exact
# address match. Both requests use short timeouts so non-DigitalOcean hosts fail
# closed without delaying a deployment for long.
reserved_ipv4_active="$(
  curl --fail --silent --show-error --max-time 2 \
    "${metadata_base}/reserved_ip/ipv4/active" 2>/dev/null \
    | tr -d '\r\n' \
    || true
)"
[ "${reserved_ipv4_active}" = true ] || {
  printf 'No active DigitalOcean Reserved IPv4 was reported\n' >&2
  exit 1
}

reserved_ipv4="$(
  curl --fail --silent --show-error --max-time 2 \
    "${metadata_base}/reserved_ip/ipv4/ip_address" 2>/dev/null \
    | tr -d '\r\n' \
    || true
)"
[ "${reserved_ipv4}" = "${expected_ipv4}" ] || {
  printf 'DigitalOcean Reserved IPv4 does not match the expected address\n' >&2
  exit 1
}

printf 'Verified active DigitalOcean Reserved IPv4: %s\n' "${expected_ipv4}"
