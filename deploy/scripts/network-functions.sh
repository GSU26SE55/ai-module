#!/usr/bin/env bash

# Shared network checks for production preflight scripts. These functions read
# complete command output instead of using `grep -q` in a pipe. With pipefail,
# an early grep exit can send SIGPIPE to `ip` and turn a valid match into a
# false failure.

local_ipv4_is_configured() {
  local expected_ipv4="${1:?expected IPv4 address is required}"

  ip -o -4 address show \
    | awk -v expected="${expected_ipv4}" '
        {
          split($4, address, "/")
          if (address[1] == expected) {
            found = 1
          }
        }
        END { exit(found ? 0 : 1) }
      '
}

AUTHORITATIVE_IPV4_LAST_ANSWERS=""
DNS_NAMESERVER_LAST_ANSWERS=""

dns_nameservers_for_zone() {
  local zone="${1:?DNS zone is required}"
  local max_attempts="${2:-5}"
  local retry_delay_seconds="${3:-2}"
  local attempt

  DNS_NAMESERVER_LAST_ANSWERS=""

  for ((attempt = 1; attempt <= max_attempts; attempt += 1)); do
    DNS_NAMESERVER_LAST_ANSWERS="$(
      {
        dig \
          +time=3 \
          +tries=1 \
          +short \
          NS \
          "${zone}" \
          2>/dev/null \
          || true
      } \
        | sed 's/\.$//' \
        | awk 'NF == 1 && $1 ~ /^[A-Za-z0-9.-]+$/ { print tolower($1) }' \
        | sort -u
    )"

    if [[ -n "${DNS_NAMESERVER_LAST_ANSWERS}" ]]; then
      return 0
    fi

    if (( attempt < max_attempts )); then
      sleep "${retry_delay_seconds}"
    fi
  done

  return 1
}

authoritative_ipv4_matches() {
  local nameserver="${1:?nameserver is required}"
  local domain="${2:?domain is required}"
  local expected_ipv4="${3:?expected IPv4 address is required}"
  local max_attempts="${4:-5}"
  local retry_delay_seconds="${5:-2}"
  local attempt

  AUTHORITATIVE_IPV4_LAST_ANSWERS=""

  for ((attempt = 1; attempt <= max_attempts; attempt += 1)); do
    AUTHORITATIVE_IPV4_LAST_ANSWERS="$(
      {
        dig \
          +time=3 \
          +tries=1 \
          +short \
          "@${nameserver}" \
          A \
          "${domain}" \
          2>/dev/null \
          || true
      } \
        | awk '/^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$/' \
        | sort -u
    )"

    if [[ "${AUTHORITATIVE_IPV4_LAST_ANSWERS}" = "${expected_ipv4}" ]]; then
      return 0
    fi

    if (( attempt < max_attempts )); then
      sleep "${retry_delay_seconds}"
    fi
  done

  return 1
}
