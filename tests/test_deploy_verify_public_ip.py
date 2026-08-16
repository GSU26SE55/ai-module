from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[1] / "deploy" / "scripts" / "verify-public-ip.sh"
EXPECTED_IP = "168.144.48.16"

# _run_check() builds POSIX shims — chmod +x and a ':'-separated PATH — so this
# module can only run on a POSIX host. It is exercised on the ubuntu-latest CI
# runner; on Windows dev machines `bash` resolves to WSL and the shims are inert.
pytestmark = pytest.mark.skipif(
    os.name != "posix",
    reason="requires a POSIX shell environment (runs on the Linux CI runner)",
)


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)


def _run_check(
    tmp_path: Path,
    *,
    local_ip: str = "",
    reserved_active: str = "false",
    reserved_ip: str = "",
) -> subprocess.CompletedProcess[str]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _write_executable(
        bin_dir / "ip",
        """#!/usr/bin/env bash
set -eu
if [ -n "${FAKE_LOCAL_IP:-}" ]; then
  printf '2: eth0 inet %s/24 scope global eth0\\n' "${FAKE_LOCAL_IP}"
fi
""",
    )
    _write_executable(
        bin_dir / "curl",
        """#!/usr/bin/env bash
set -eu
url=''
for argument in "$@"; do
  url="${argument}"
done
case "${url}" in
  */reserved_ip/ipv4/active)
    printf '%s' "${FAKE_RESERVED_ACTIVE:-false}"
    ;;
  */reserved_ip/ipv4/ip_address)
    printf '%s' "${FAKE_RESERVED_IP:-}"
    ;;
  *)
    exit 22
    ;;
esac
""",
    )
    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{bin_dir}:{env['PATH']}",
            "FAKE_LOCAL_IP": local_ip,
            "FAKE_RESERVED_ACTIVE": reserved_active,
            "FAKE_RESERVED_IP": reserved_ip,
        }
    )
    return subprocess.run(
        ["bash", str(SCRIPT), EXPECTED_IP],
        check=False,
        capture_output=True,
        env=env,
        text=True,
    )


def test_accepts_address_assigned_to_local_interface(tmp_path: Path) -> None:
    result = _run_check(tmp_path, local_ip=EXPECTED_IP)

    assert result.returncode == 0
    assert "Verified local public IPv4" in result.stdout


def test_accepts_matching_active_digitalocean_reserved_ip(tmp_path: Path) -> None:
    result = _run_check(
        tmp_path,
        local_ip="178.128.95.176",
        reserved_active="true",
        reserved_ip=EXPECTED_IP,
    )

    assert result.returncode == 0
    assert "Verified active DigitalOcean Reserved IPv4" in result.stdout


def test_rejects_mismatched_digitalocean_reserved_ip(tmp_path: Path) -> None:
    result = _run_check(
        tmp_path,
        local_ip="178.128.95.176",
        reserved_active="true",
        reserved_ip="203.0.113.10",
    )

    assert result.returncode != 0
    assert "does not match" in result.stderr


def test_rejects_inactive_digitalocean_reserved_ip(tmp_path: Path) -> None:
    result = _run_check(
        tmp_path,
        local_ip="178.128.95.176",
        reserved_active="false",
        reserved_ip=EXPECTED_IP,
    )

    assert result.returncode != 0
    assert "No active" in result.stderr
