from __future__ import annotations

import os
import shlex
import subprocess
from pathlib import Path

NETWORK_FUNCTIONS = (
    Path(__file__).parents[1] / "deploy" / "scripts" / "network-functions.sh"
)
EXPECTED_IP = "127.0.0.1"


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)


def _run_function(
    tmp_path: Path,
    command: str,
    *,
    ip_script: str | None = None,
    dig_script: str | None = None,
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()

    if ip_script is not None:
        _write_executable(bin_dir / "ip", ip_script)
    if dig_script is not None:
        _write_executable(bin_dir / "dig", dig_script)

    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}:{env['PATH']}"
    if extra_env:
        env.update(extra_env)

    script = f"""
set -Eeuo pipefail
source {shlex.quote(str(NETWORK_FUNCTIONS))}
{command}
"""
    return subprocess.run(
        ["bash", "-c", script],
        check=False,
        capture_output=True,
        env=env,
        text=True,
    )


def test_local_ipv4_match_consumes_full_ip_output_without_sigpipe(
    tmp_path: Path,
) -> None:
    result = _run_function(
        tmp_path,
        f"local_ipv4_is_configured {EXPECTED_IP}",
        ip_script="""#!/usr/bin/env bash
set -eu
printf '1: lo inet 127.0.0.1/8 scope host lo\\n'
for ((index = 1; index <= 20000; index += 1)); do
  printf '2: eth0 inet 10.0.%d.%d/24 scope global eth0\\n' \\
    "$((index % 255))" "$(((index + 1) % 255))"
done
""",
    )

    assert result.returncode == 0, result.stderr


def test_local_ipv4_rejects_missing_address(tmp_path: Path) -> None:
    result = _run_function(
        tmp_path,
        f"local_ipv4_is_configured {EXPECTED_IP}",
        ip_script="""#!/usr/bin/env bash
set -eu
printf '2: eth0 inet 10.20.0.2/24 scope global eth0\\n'
""",
    )

    assert result.returncode != 0


def test_authoritative_dns_retries_transient_empty_answers(tmp_path: Path) -> None:
    counter = tmp_path / "dig-attempts"
    result = _run_function(
        tmp_path,
        (
            "authoritative_ipv4_matches "
            "ns1.example.test ai.example.test 168.144.48.16 3 0"
        ),
        dig_script="""#!/usr/bin/env bash
set -eu
attempt=0
if test -f "${DIG_COUNTER}"; then
  attempt="$(cat "${DIG_COUNTER}")"
fi
attempt="$((attempt + 1))"
printf '%s' "${attempt}" >"${DIG_COUNTER}"
if test "${attempt}" -ge 3; then
  printf '168.144.48.16\\n'
else
  exit 9
fi
""",
        extra_env={"DIG_COUNTER": str(counter)},
    )

    assert result.returncode == 0, result.stderr
    assert counter.read_text(encoding="utf-8") == "3"


def test_authoritative_dns_rejects_persistent_wrong_answer(tmp_path: Path) -> None:
    counter = tmp_path / "dig-attempts"
    result = _run_function(
        tmp_path,
        (
            "authoritative_ipv4_matches "
            "ns1.example.test ai.example.test 168.144.48.16 3 0"
        ),
        dig_script="""#!/usr/bin/env bash
set -eu
attempt=0
if test -f "${DIG_COUNTER}"; then
  attempt="$(cat "${DIG_COUNTER}")"
fi
printf '%s' "$((attempt + 1))" >"${DIG_COUNTER}"
printf '203.0.113.10\\n'
""",
        extra_env={"DIG_COUNTER": str(counter)},
    )

    assert result.returncode != 0
    assert counter.read_text(encoding="utf-8") == "3"


def test_nameserver_lookup_retries_transient_dig_failure(tmp_path: Path) -> None:
    counter = tmp_path / "dig-attempts"
    result = _run_function(
        tmp_path,
        "dns_nameservers_for_zone example.test 3 0",
        dig_script="""#!/usr/bin/env bash
set -eu
attempt=0
if test -f "${DIG_COUNTER}"; then
  attempt="$(cat "${DIG_COUNTER}")"
fi
attempt="$((attempt + 1))"
printf '%s' "${attempt}" >"${DIG_COUNTER}"
if test "${attempt}" -ge 3; then
  printf 'NS1.EXAMPLE.TEST.\\nns2.example.test.\\n'
else
  exit 9
fi
""",
        extra_env={"DIG_COUNTER": str(counter)},
    )

    assert result.returncode == 0, result.stderr
    assert counter.read_text(encoding="utf-8") == "3"
