#!/usr/bin/env bash
set -Eeuo pipefail

readonly INTERFACE="wg0"
readonly LISTEN_PORT="51820"
readonly WIREGUARD_DIR="/etc/wireguard"
readonly PRIVATE_KEY_FILE="${WIREGUARD_DIR}/solar-private.key"
readonly PUBLIC_KEY_FILE="${WIREGUARD_DIR}/solar-public.key"
readonly CONFIG_FILE="${WIREGUARD_DIR}/${INTERFACE}.conf"
TEMPORARY_CONFIG=""

cleanup() {
  if [[ -n "${TEMPORARY_CONFIG}" ]]; then
    rm -f -- "${TEMPORARY_CONFIG}"
  fi
}

trap cleanup EXIT

usage() {
  cat <<'EOF'
Usage:
  sudo ./configure-ai-wireguard.sh init <local-wireguard-ip>
  sudo ./configure-ai-wireguard.sh configure <local-wireguard-ip> <peer-public-key> <peer-endpoint>

Allowed tunnel addresses:
  Backend VPS: 10.20.0.1
  AI VPS:      10.20.0.2

Examples:
  sudo ./configure-ai-wireguard.sh init 10.20.0.2
  sudo ./configure-ai-wireguard.sh configure 10.20.0.2 '<BACKEND_PUBLIC_KEY>' 10.104.0.4:51820
EOF
}

die() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

require_root() {
  [[ "${EUID}" -eq 0 ]] || die "run this script with sudo"
}

require_commands() {
  local command_name
  for command_name in wg wg-quick systemctl install mktemp cat ip; do
    command -v "${command_name}" >/dev/null 2>&1 || die "missing required command: ${command_name}"
  done
}

peer_ip_for() {
  case "$1" in
    10.20.0.1) printf '10.20.0.2\n' ;;
    10.20.0.2) printf '10.20.0.1\n' ;;
    *) die "local WireGuard IP must be 10.20.0.1 or 10.20.0.2" ;;
  esac
}

ensure_keys() {
  install -d -m 0700 "${WIREGUARD_DIR}"
  if [[ ! -s "${PRIVATE_KEY_FILE}" || ! -s "${PUBLIC_KEY_FILE}" ]]; then
    umask 077
    wg genkey >"${PRIVATE_KEY_FILE}"
    wg pubkey <"${PRIVATE_KEY_FILE}" >"${PUBLIC_KEY_FILE}"
  fi
  chmod 0600 "${PRIVATE_KEY_FILE}" "${PUBLIC_KEY_FILE}"
}

install_config() {
  local local_ip="$1"
  local peer_public_key="${2:-}"
  local peer_endpoint="${3:-}"
  local peer_ip private_key

  peer_ip="$(peer_ip_for "${local_ip}")"
  private_key="$(cat "${PRIVATE_KEY_FILE}")"
  TEMPORARY_CONFIG="$(mktemp "/tmp/${INTERFACE}.XXXXXX.conf")"

  {
    printf '[Interface]\n'
    printf 'Address = %s/32\n' "${local_ip}"
    printf 'ListenPort = %s\n' "${LISTEN_PORT}"
    printf 'PrivateKey = %s\n' "${private_key}"

    if [[ -n "${peer_public_key}" ]]; then
      printf '\n[Peer]\n'
      printf 'PublicKey = %s\n' "${peer_public_key}"
      printf 'AllowedIPs = %s/32\n' "${peer_ip}"
      printf 'Endpoint = %s\n' "${peer_endpoint}"
      printf 'PersistentKeepalive = 25\n'
    fi
  } >"${TEMPORARY_CONFIG}"

  wg-quick strip "${TEMPORARY_CONFIG}" >/dev/null
  install -m 0600 "${TEMPORARY_CONFIG}" "${CONFIG_FILE}"
  rm -f -- "${TEMPORARY_CONFIG}"
  TEMPORARY_CONFIG=""
  systemctl enable "wg-quick@${INTERFACE}.service" >/dev/null
  systemctl restart "wg-quick@${INTERFACE}.service"
}

show_status() {
  printf 'Public key (safe to share): %s\n' "$(cat "${PUBLIC_KEY_FILE}")"
  ip -brief address show dev "${INTERFACE}"
  wg show "${INTERFACE}"
}

main() {
  require_root
  require_commands

  local operation="${1:-}"
  local local_ip="${2:-}"
  [[ -n "${operation}" && -n "${local_ip}" ]] || { usage; exit 2; }
  peer_ip_for "${local_ip}" >/dev/null
  ensure_keys

  case "${operation}" in
    init)
      [[ "$#" -eq 2 ]] || { usage; exit 2; }
      install_config "${local_ip}"
      ;;
    configure)
      [[ "$#" -eq 4 ]] || { usage; exit 2; }
      local peer_public_key="$3"
      local peer_endpoint="$4"
      [[ "${peer_public_key}" =~ ^[A-Za-z0-9+/]{43}=$ ]] || die "peer public key has an invalid WireGuard format"
      [[ "${peer_endpoint}" =~ ^[A-Za-z0-9.-]+:51820$ ]] || die "peer endpoint must use host-or-ip:51820 format"
      install_config "${local_ip}" "${peer_public_key}" "${peer_endpoint}"
      ;;
    *)
      usage
      exit 2
      ;;
  esac

  show_status
}

main "$@"
