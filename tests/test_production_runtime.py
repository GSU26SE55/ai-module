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

    assert alloy["user"] == "473:10001"
    assert alloy["group_add"] == [
        "${AI_DOCKER_SOCKET_GID:?AI_DOCKER_SOCKET_GID must match the Docker socket group}"
    ]
    assert "--server.http.listen-addr=0.0.0.0:12345" in alloy["command"]
    assert alloy["ports"] == ["${AI_MONITORING_BIND_IP}:12345:12345"]
    assert "--storage.path=/var/lib/alloy/data" in alloy["command"]
    assert alloy["healthcheck"]["test"][:3] == ["CMD", "/bin/bash", "-ec"]
    assert "/-/ready" in alloy["healthcheck"]["test"][3]


def test_caddy_exposes_application_metrics_only_to_wireguard_peer():
    compose = yaml.safe_load(Path("docker-compose.prod.yml").read_text())
    caddyfile = Path("deploy/caddy/Caddyfile").read_text()

    assert compose["services"]["caddy"]["environment"]["PLATFORM_WIREGUARD_IPV4"]
    assert "@metrics path /metrics /metrics/*" in caddyfile
    assert "remote_ip {$PLATFORM_WIREGUARD_IPV4}" in caddyfile
    assert 'respond "Forbidden" 403' in caddyfile


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
