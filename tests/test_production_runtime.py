"""Production lifecycle, manifest and standard gRPC health contracts."""

from pathlib import Path
from unittest.mock import Mock

import grpc
import yaml
from fastapi.testclient import TestClient
from grpc_health.v1 import health_pb2, health_pb2_grpc

from src.core.artifact_manifest import verify_model_manifest


def test_alloy_runtime_has_storage_socket_permissions_and_readiness_probe():
    compose = yaml.safe_load(Path("docker-compose.prod.yml").read_text())
    alloy = compose["services"]["alloy"]

    assert alloy["profiles"] == ["central-observability"]
    assert alloy["user"] == "473:10001"
    assert alloy["group_add"] == ["${AI_DOCKER_SOCKET_GID:-0}"]
    assert "--server.http.listen-addr=0.0.0.0:12345" in alloy["command"]
    assert alloy["ports"] == ["${AI_MONITORING_BIND_IP:-127.0.0.1}:12345:12345"]
    assert "--storage.path=/var/lib/alloy/data" in alloy["command"]
    assert alloy["healthcheck"]["test"][:3] == ["CMD", "/bin/bash", "-ec"]
    assert "/-/ready" in alloy["healthcheck"]["test"][3]


def test_shared_host_caddy_uses_loopback_upstreams_and_private_metrics():
    compose = yaml.safe_load(Path("docker-compose.prod.yml").read_text())
    caddyfile = Path("deploy/caddy/Caddyfile").read_text()
    ai_module = compose["services"]["ai-module"]

    assert "caddy" not in compose["services"]
    assert ai_module["ports"] == [
        "127.0.0.1:18000:8000",
        "127.0.0.1:15051:50051",
    ]
    assert ai_module["extra_hosts"] == [
        "${AI_PUBLIC_DOMAIN:?AI_PUBLIC_DOMAIN is required}:host-gateway"
    ]
    assert "ai.solaris.io.vn {" in caddyfile
    assert "@metrics path /metrics /metrics/*" in caddyfile
    assert "remote_ip 10.20.0.1" in caddyfile
    assert "reverse_proxy 127.0.0.1:18000" in caddyfile
    assert "reverse_proxy @grpc h2c://127.0.0.1:15051" in caddyfile
    assert 'respond "Forbidden" 403' in caddyfile


def test_shared_host_runtime_keeps_access_logs_for_alloy_loki_gate():
    dockerfile = Path("Dockerfile").read_text()
    observability_script = Path("deploy/scripts/verify-observability.sh").read_text()

    assert "--no-access-log" not in dockerfile
    assert 'container=\\"solar-ai-module\\"' in observability_script
    assert 'https://${public_domain}/ready?marker=${observability_marker}' in (
        observability_script
    )


def test_central_observability_services_are_opt_in_profiles():
    compose = yaml.safe_load(Path("docker-compose.prod.yml").read_text())

    assert "profiles" not in compose["services"]["ai-module"]
    for service in ("node-exporter", "cadvisor", "alloy"):
        assert compose["services"][service]["profiles"] == [
            "central-observability"
        ]


def test_preflight_requires_the_installed_shared_host_caddy_contract():
    script = Path("deploy/scripts/preflight.sh").read_text()

    assert 'host_caddyfile="/etc/caddy/Caddyfile"' in script
    assert "systemctl is-active --quiet caddy" in script
    assert 'reverse_proxy 127.0.0.1:18000' in script
    assert 'reverse_proxy @grpc h2c://127.0.0.1:15051' in script
    assert '--resolve "${public_domain}:443:127.0.0.1"' in script
    assert '"${root}/data/caddy/data"' not in script


def test_trusted_production_job_targets_the_shared_r3_lock_and_credentials():
    pipeline = Path("deploy/jenkins/production.Jenkinsfile.example").read_text()

    assert "Deploy AI on shared R3" in pipeline
    assert "solar-r3-ai-prod" in pipeline
    assert "ai-r3-target" in pipeline
    assert "ai-r3-deploy-ssh" in pipeline
    assert "ai-r3-known-hosts" in pipeline
    assert "ai-github-read" not in pipeline
    assert "solar-vps2-prod" not in pipeline


def test_deploy_arms_rollback_only_before_runtime_mutation():
    script = Path("deploy/scripts/deploy.sh").read_text()

    preflight_position = script.index('"${release_dir}/deploy/scripts/preflight.sh"')
    pull_position = script.index("compose pull")
    trap_position = script.index("trap rollback_on_failure EXIT")
    up_position = script.index("compose up -d --remove-orphans --wait")

    assert preflight_position < pull_position < trap_position < up_position
    assert (
        '"${release_dir}/deploy/scripts/rollback.sh" "${previous_release}"'
        in script
    )

    rollback_script = Path("deploy/scripts/rollback.sh").read_text()
    assert '"${script_dir}/preflight.sh" "${target}"' in rollback_script
    assert "require_alloy_metrics=false" in rollback_script
    assert '"${script_dir}/verify-observability.sh"' in rollback_script


def test_preflight_proves_wireguard_without_privileged_handshake_query():
    script = Path("deploy/scripts/preflight.sh").read_text()

    route_check = 'ip -4 route get "${platform_wireguard_ipv4}"'
    loki_probe = '"http://${platform_wireguard_ipv4}:3100/ready"'

    assert "latest-handshakes" not in script
    assert route_check in script
    assert loki_probe in script
    assert "--connect-timeout 5 --max-time 10" in script
    assert script.index(route_check) < script.index(loki_probe)
    assert 'if [[ "${observability_mode}" == central ]]' in script


def test_standalone_runtime_does_not_require_wireguard_or_loki():
    preflight = Path("deploy/scripts/preflight.sh").read_text()
    verifier = Path("deploy/scripts/verify-observability.sh").read_text()

    assert "AI_OBSERVABILITY_MODE must be standalone or central" in preflight
    assert "compose_profile_args+=(--profile central-observability)" in preflight
    assert "AI standalone runtime verified" in verifier
    assert 'if exc.code != 403:' in verifier


def test_committed_model_manifest_verifies():
    result = verify_model_manifest()
    assert result["verified"] is True
    assert result["artifacts"] >= 21


def test_standard_grpc_health_is_serving():
    from src.grpc_server import create_server

    server = create_server(port=0, host="127.0.0.1")
    port = server._ai_bound_port
    server.start()
    channel = grpc.insecure_channel(f"127.0.0.1:{port}")
    response = health_pb2_grpc.HealthStub(channel).Check(
        health_pb2.HealthCheckRequest(service="aimodule.v1.AiService"), timeout=5
    )
    assert response.status == health_pb2.HealthCheckResponse.SERVING
    channel.close()
    server.stop(grace=None)


def test_fastapi_lifespan_starts_and_stops_grpc(monkeypatch):
    import main

    fake_server = Mock()
    fake_server.stop.return_value.wait.return_value = None
    monkeypatch.setenv("AI_ENABLE_GRPC", "true")
    monkeypatch.setattr(main, "verify_model_manifest", Mock())
    monkeypatch.setattr(main, "load_models", Mock())
    monkeypatch.setattr(main, "create_server", Mock(return_value=fake_server))
    monkeypatch.setattr(main, "mark_server_not_serving", Mock())

    with TestClient(main.app) as client:
        assert client.get("/live").status_code == 200

    fake_server.start.assert_called_once_with()
    main.mark_server_not_serving.assert_called_once_with(fake_server)
    fake_server.stop.assert_called_once_with(grace=10)
