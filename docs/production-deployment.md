# AI Module production deployment

This is the source of truth for deploying `GSU26SE55/ai-module` to R3. R3 runs
Jenkins and AI together. The initial standalone release does not depend on a
Backend or observability VPS. AI runs with Docker Compose, while one host-level Caddy serves both
`jenkins.solars.io.vn` and `ai.solaris.io.vn`. A successful, non-PR Jenkins build
of `main` is the only event that may request a production deployment.

## 1. Production contract

R3 standalone mode runs one required container in the `solar-ai` Compose
project. Three central-observability containers are opt-in and remain stopped
until that remote platform is provisioned:

| Container | Purpose | Exposure |
|---|---|---|
| `solar-ai-module` | FastAPI, gRPC, NASA/LFP models, embedded ChromaDB/RAG | loopback `127.0.0.1:18000`, `127.0.0.1:15051` |
| `solar-ai-node-exporter` | Optional VPS CPU/RAM/disk metrics | central mode, WireGuard only: `9100` |
| `solar-ai-cadvisor` | Optional container metrics | central mode, WireGuard only: `8082` |
| `solar-ai-alloy` | Optional Docker log shipping and self-metrics | central mode, outbound to Loki; WireGuard-only `12345` |

Both backend transports use the same origin:

- primary gRPC: `https://ai.solaris.io.vn:443` over HTTP/2;
- fallback REST: `https://ai.solaris.io.vn`;
- host Caddy routes gRPC to `h2c://127.0.0.1:15051` and all other AI traffic to
  FastAPI on `127.0.0.1:18000`.

The raw ports are never bound to a public interface, and the Compose project
must not publish `80` or `443`. ChromaDB is embedded in the AI process rather
than deployed as another container. The immutable image contains a
checksum-verified knowledge-base seed; mutable KB, history and feedback state
live under `/opt/solar-ai/data`.

## 2. Blocking DNS check

The intended record is:

```text
ai.solaris.io.vn.  A  116.118.6.30
```

`jenkins.solars.io.vn` uses the same A record. Replace `116.118.6.30` everywhere
if R3 changes. Do not add an AAAA record unless IPv6 is configured end-to-end,
Caddy listens on it and the firewall also permits it.

At the follow-up audit on **2026-08-23**, public resolvers returned:

```text
ai.solaris.io.vn     -> 116.118.6.30
jenkins.solars.io.vn -> 116.118.6.30
```

The AAAA result was empty. DNS was ready at that audit, but it remains a
deployment-time invariant rather than a one-time assumption. Verify from any
Internet-connected machine before the first release and after every IP change:

```bash
dig +short NS solaris.io.vn
for ns in ns1.zonedns.vn ns2.zonedns.vn ns3.zonedns.vn ns4.zonedns.vn; do
  dig +short "@${ns}" A ai.solaris.io.vn
done
dig +short AAAA ai.solaris.io.vn
```

The four authoritative A answers must be identical to R3 and the AAAA result
must be empty. The deployment preflight repeats these checks, verifies the IP
belongs to the host, and refuses to touch the running release when they fail.

## 3. R3 capacity and base packages

Use Ubuntu 24.04 LTS x86_64. Because R3 also builds images in Jenkins, 8 vCPU,
16 GiB RAM, at least 120 GiB SSD and 4 GiB swap are recommended. No GPU is
required. The AI container is limited to 3.25 CPU/5 GiB; exporters use separate
small limits. Preflight requires at least 10 GiB free disk and 2 GiB currently
available RAM. Keep Jenkins at one executor and monitor memory/disk pressure.
PostgreSQL, RabbitMQ, Redis, MinIO, Prometheus and Grafana remain on R4.

Before provisioning, take a provider snapshot. Then install base tools:

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl dnsutils gnupg jq wireguard
```

Install Docker Engine and the Compose v2 plugin from Docker's official Ubuntu
repository, not Ubuntu's obsolete `docker.io` package. Confirm:

```bash
docker version
docker compose version
```

Install Caddy, Jenkins, Cosign and the pinned CI toolchain on R3. Keep Caddy on
the host; never add it back to the AI Compose project.

## 4. Network and firewall

Use the VPS provider firewall as well as UFW. Docker-published ports can bypass
ordinary UFW forwarding rules, so UFW alone is not the production boundary.

Inbound rules for R3:

| Protocol/port | Source | Reason |
|---|---|---|
| TCP 22 | approved admin IP only | administration; Jenkins deploy uses loopback SSH |
| TCP 80 | all IPv4 | forced ACME HTTP-01 and HTTP-to-HTTPS redirect |
| TCP 443 | all IPv4 | Jenkins UI plus AI REST/gRPC without a client VPN |
| UDP 51820 | exact observability peer public IP, once known | optional private Backend/AI and observability path |

Do not create public rules for `15051`, `18000`, `8000`, `50051`, `8082`,
`9100` or `12345`. Ports `15051` and `18000` must appear only on
`127.0.0.1`. The Caddy configuration disables TLS-ALPN challenges, so public
port 80 remains required for certificate renewal.

Standalone mode requires no WireGuard peer and no UDP `51820` firewall rule.
After the central Prometheus/Loki host and its public IP are known, configure
WireGuard as `10.20.0.1/32` on that host and `10.20.0.2/32` on R3. Only the two
peer addresses are routed. Allow the central host to
scrape only:

- `https://ai.solaris.io.vn/metrics/` for application HTTP/gRPC metrics;
- `10.20.0.2:9100/metrics` for node-exporter;
- `10.20.0.2:8082/metrics` for cAdvisor;
- `10.20.0.2:12345/metrics` for Alloy health/self-metrics.

The Caddy route returns `403` for `/metrics` unless the remote address is the
Backend WireGuard peer. `/live` and `/ready` remain available through normal
HTTPS. Alloy pushes logs to `http://10.20.0.1:3100/loki/api/v1/push`.

Do not invent or preconfigure a peer public IP. Once the central host exists,
use R3 `116.118.6.30` and the actual peer endpoint, restricted to UDP 51820 in
both provider firewall and UFW. Bootstrap the peer without ever copying its
private key:

```bash
sudo apt-get install -y wireguard
sudo deploy/scripts/configure-ai-wireguard.sh init 10.20.0.2

# After exchanging only the two public keys:
sudo deploy/scripts/configure-ai-wireguard.sh configure \
  10.20.0.2 "$BACKEND_WG_PUBLIC_KEY" "$BACKEND_PUBLIC_IP:51820"
```

The provider firewall and UFW must accept UDP `51820` only from the exact peer
public IP. On `wg0`, accept TCP `443`, `9100`, `8082` and `12345` only from
`10.20.0.1`; the central host accepts `3100` only from `10.20.0.2`. Central mode
remains fail-closed until the peer and Loki bridge are active. Standalone mode
does not run or validate these optional services.

The Jenkins SSH account intentionally has no `CAP_NET_ADMIN` and must not be
granted `sudo` merely to run `wg show`. Production preflight instead verifies
that the Backend peer address is routed through `wg0`, then performs a bounded
HTTP readiness request to Loki at `10.20.0.1:3100`. Because only the peer `/32`
is routed through `wg0`, a successful response proves the encrypted data path
is usable and refreshes an idle WireGuard handshake.

## 5. One-time R3 provisioning

Create a dedicated SSH account. Its key must be key-only and used only by
Jenkins. Docker group membership is root-equivalent, so never share this account.

```bash
sudo adduser --disabled-password --gecos '' deploy
sudo usermod -aG docker deploy
sudo groupadd --gid 10001 ai-runtime
sudo usermod -aG ai-runtime deploy
```

If GID `10001` already exists, reuse its existing group instead of creating a
duplicate. Log out and back in after changing group memberships. Provision the
tree, replacing `deploy:ai-runtime` with the actual names if needed:

```bash
sudo install -d -o deploy -g ai-runtime -m 2770 \
  /opt/solar-ai/config \
  /opt/solar-ai/secrets \
  /opt/solar-ai/incoming \
  /opt/solar-ai/releases \
  /opt/solar-ai/data/alloy \
  /opt/solar-ai/data/kb \
  /opt/solar-ai/data/prescription-history \
  /opt/solar-ai/data/classification-feedback
```

The final layout is:

```text
/opt/solar-ai/
├── config/
│   ├── host.env
│   ├── allowed-image-repository
│   └── cosign.pub
├── secrets/ai.env
├── data/
│   ├── alloy/
│   ├── kb/
│   ├── prescription-history/
│   └── classification-feedback/
├── incoming/
└── releases/
```

Create `/opt/solar-ai/config/host.env` from `deploy/host.env.example`. For the
first R3-only release use standalone mode:

```dotenv
AI_PUBLIC_DOMAIN=ai.solaris.io.vn
AI_DNS_ZONE=solaris.io.vn
AI_PUBLIC_IPV4=116.118.6.30
AI_OBSERVABILITY_MODE=standalone
AI_SECRETS_FILE=/opt/solar-ai/secrets/ai.env
```

Only after the central host is known, change the mode to `central` and append
`AI_MONITORING_BIND_IP`, `PLATFORM_WIREGUARD_IPV4`, and `LOKI_PUSH_URL` using
the actual peer configuration. The deploy scripts then enable the
`central-observability` Compose profile automatically.

In central mode, `AI_DOCKER_SOCKET_GID` must be the numeric group ID of the
Docker socket on R3. Do not assume that it is always `988`; obtain the value on
that host and put the exact result in `host.env`:

```bash
stat -c '%g' /var/run/docker.sock
```

The production preflight rejects the deployment when this value is missing or
does not match the socket. Alloy runs as UID `473`, uses the shared
`ai-runtime` GID `10001` for persistent storage, and receives this Docker group
only as a supplemental group for container discovery.

Create `/opt/solar-ai/secrets/ai.env` from `deploy/ai.env.example`. At least one
of `DEEPSEEK_API_KEY`, `GEMINI_API_KEY` or `ANTHROPIC_API_KEY` must be non-empty.
Do not quote values unless the value itself needs quotes. Then:

```bash
sudo chown deploy:ai-runtime /opt/solar-ai/config/host.env \
  /opt/solar-ai/secrets/ai.env
sudo chmod 0640 /opt/solar-ai/config/host.env
sudo chmod 0600 /opt/solar-ai/secrets/ai.env
```

`/opt/solar-ai/config/allowed-image-repository` must contain exactly the
lower-case repository without tag/digest:

```text
ghcr.io/gsu26se55/ai-module
```

Copy the public half of the Jenkins Cosign key to
`/opt/solar-ai/config/cosign.pub`. Never copy the private key to R3. Log in to
GHCR once as `deploy` with a read-only robot/PAT so Compose can pull images:

```bash
printf '%s' 'READ_ONLY_GHCR_TOKEN' | docker login ghcr.io \
  --username 'ROBOT_OR_GITHUB_USER' --password-stdin
```

Delete the token from shell history if it was entered interactively. Prefer a
short-lived secret passed through a protected terminal rather than a literal as
shown in the placeholder.

## 6. Caddy TLS and automatic verification

`deploy/caddy/Caddyfile` is the canonical AI site block. Merge that block into
the existing host `/etc/caddy/Caddyfile` beside the Jenkins site; do not replace
or delete the Jenkins block. Then run:

```bash
sudo caddy fmt --overwrite /etc/caddy/Caddyfile
sudo caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
sudo systemctl reload caddy
```

Caddy must route REST to `127.0.0.1:18000`, gRPC h2c to
`127.0.0.1:15051`, and allow `/metrics` only from `10.20.0.1`. Caddy's
certificate state remains under the host package's data directory, not under
`/opt/solar-ai`.

Standalone deployment succeeds only after all of the following pass:

1. host Caddy is active and contains the exact shared-host routing contract;
2. every authoritative DNS server returns only the configured R3 IPv4;
   transient authoritative DNS failures are retried five times before the
   deployment is rejected;
3. all model/RAG artifact checksums;
4. direct `/live`, `/ready` and real REST inference;
5. direct standard/custom gRPC health plus NASA and LFP inference;
6. the same REST and gRPC tests through host Caddy with the real certificate;
7. Compose health for the AI container and public denial of `/metrics`.

Central mode adds the WireGuard route, Loki readiness, exporter and end-to-end
log delivery checks to this gate.

The AI container maps the production FQDN to Docker's host gateway for the TLS
smoke. It therefore validates certificate hostname, trust, HTTP/2 and host
Caddy routing without depending on public hairpin routing. Failure triggers
automatic rollback to the previous immutable release.

## 7. Backend production settings

The backend production chart already supports this topology. BatteryService
uses gRPC primary plus HTTPS fallback, while TicketService uses gRPC. The
production overlay at
`deploy/helm/solar-battery/values-production.yaml` contains this contract and
the backend deploy script also overrides the three endpoint values from R4
`host.env` so a stale/default address cannot silently reach production:

```yaml
config:
  Ai__Enabled: "true"
  Ai__GrpcAddress: "https://ai.solaris.io.vn"
  Ai__HttpBaseUrl: "https://ai.solaris.io.vn"
  Ai__TimeoutSeconds: "5"
  Ai__IntervalMinutes: "5"
  Ai__MinReadings: "30"
  Ai__MaxScanReadings: "60"
  Ai__PrescriptionEnabled: "true"

  TicketAi__Enabled: "true"
  TicketAi__BatteryServiceBaseUrl: "http://batteryservice:80"
  TicketAi__AiGrpcAddress: "https://ai.solaris.io.vn"
  TicketAi__BatteryGrpcAddress: "http://batteryservice:8081"
  TicketAi__TimeoutSeconds: "5"
  TicketAi__MaxDuplicateCandidates: "10"
```

The base chart publishes BatteryService's HTTP/2 gRPC listener as Service port
`8081`, so `TicketAi__BatteryGrpcAddress=http://batteryservice:8081` remains
cluster-internal. Do not expose that port through R4 Caddy or the provider
firewall.

Render the backend chart and inspect the generated ConfigMap before upgrading:

```bash
helm template solar-backend deploy/helm/solar-battery \
  -f deploy/helm/solar-battery/values.yaml \
  -f deploy/helm/solar-battery/values-vps-small.yaml \
  -f deploy/helm/solar-battery/values-production.yaml \
  | grep -E 'Ai__|TicketAi__'
```

After `helm upgrade --install`, verify what the live pods actually received:

```bash
kubectl -n solar-prod rollout status deployment/batteryservice
kubectl -n solar-prod rollout status deployment/ticketservice
kubectl -n solar-prod exec deploy/batteryservice -- printenv \
  | grep -E '^Ai__(Enabled|GrpcAddress|HttpBaseUrl)='
kubectl -n solar-prod exec deploy/ticketservice -- printenv \
  | grep -E '^TicketAi__(Enabled|AiGrpcAddress)='
```

If backend is temporarily deployed with Docker Compose instead of k3s, put the
same ASP.NET nested keys in R4 `/opt/solar/.env.prod`; the production Compose
loads them through `env_file` and does not translate the short `AI_*` aliases
used by the development Compose:

```dotenv
Ai__Enabled=true
Ai__GrpcAddress=https://ai.solaris.io.vn
Ai__HttpBaseUrl=https://ai.solaris.io.vn
Ai__TimeoutSeconds=5
Ai__IntervalMinutes=5
Ai__MinReadings=30
Ai__MaxScanReadings=60
Ai__PrescriptionEnabled=true

TicketAi__Enabled=true
TicketAi__BatteryServiceBaseUrl=http://batteryservice:8080
TicketAi__AiGrpcAddress=https://ai.solaris.io.vn
TicketAi__BatteryGrpcAddress=http://batteryservice:8081
TicketAi__TimeoutSeconds=5
TicketAi__MaxDuplicateCandidates=10
```

Do not append `/api` or a method path. For gRPC, .NET selects HTTP/2/TLS from
the `https://` URI. For REST fallback, typed HttpClient appends the existing
FastAPI paths. Restart BatteryService and TicketService only after AI TLS smoke
passes.

Because the current backend does not send an API token or mTLS client
certificate, do not add Caddy Basic Auth to these routes. Keep application
metrics restricted by WireGuard and apply rate limiting/abuse controls at the
public edge. A future mTLS/shared-token design must update both backend clients
and AI ingress atomically.

## 8. Jenkins architecture

Use two jobs:

1. `solar-ai-ci`: Multibranch Pipeline loaded from repository `Jenkinsfile`.
   It receives no registry-write, Cosign-private or VPS credentials. PRs and
   branches run checks only. A non-PR `main` build requests job 2.
2. `solar-ai-production`: centrally managed Pipeline with the reviewed content
   of `deploy/jenkins/production.Jenkinsfile.example`. Its script is pasted into
   Jenkins rather than loaded from a PR-controlled workspace.

The Docker Linux agent labeled `docker-linux` needs Python 3.11 + venv, Docker
Engine/Compose/Buildx, Git, ShellCheck, Trivy, Syft, Cosign, tar and OpenSSH. R3
uses its built-in node for this student deployment. Keep it at one executor,
bind Jenkins HTTP to `127.0.0.1:8080`, expose it only through Caddy, and
understand that Docker group membership is root-equivalent.

The source/workspace Trivy gate rejects every detected HIGH or CRITICAL issue.
The final-image gates use `--ignore-unfixed`: they still reject actionable
HIGH/CRITICAL findings that have an upstream fix, while reporting but not
blocking on Debian findings for which no fixed package exists yet. Re-scan on
every build and refresh the pinned base-image digest as soon as the vendor
publishes a fix; do not add CVE IDs to an ignore file merely to make a build
green.

Install these Jenkins plugins:

- Pipeline and Pipeline: Multibranch;
- Git and GitHub Branch Source;
- Credentials Binding and SSH Agent;
- Lockable Resources;
- JUnit.

Create credentials with these exact IDs, scoped to the production job/folder
where possible:

| ID | Jenkins type | Value |
|---|---|---|
| `ai-registry-host` | Secret text | `ghcr.io` |
| `ai-image-repository` | Secret text | `ghcr.io/gsu26se55/ai-module` |
| `ai-registry-write` | Username/password | GHCR push-capable robot/user token |
| `ai-cosign-private-key` | Secret file | encrypted Cosign private key |
| `ai-cosign-public-key` | Secret file | matching public key |
| `ai-cosign-password` | Secret text | Cosign key password |
| `ai-r3-target` | Secret text | `deploy@127.0.0.1` |
| `ai-r3-deploy-ssh` | SSH username/private key | user `deploy`, key restricted to loopback if supported |
| `ai-r3-known-hosts` | Secret file | pinned localhost host key verified against R3's host public key |

Never build `known_hosts` with `StrictHostKeyChecking=no`. From a trusted admin
session, compare R3's `/etc/ssh/ssh_host_ed25519_key.pub` fingerprint with the
localhost entry before uploading it to Jenkins. Do not target R3's public IP
from a job already running on R3.

### Configure `solar-ai-ci`

1. New Item → Multibranch Pipeline → name `solar-ai-ci`.
2. Add the public GitHub branch source for `GSU26SE55/ai-module`. No checkout
   credential is required. A separately scoped read-only GitHub API credential
   may be added later only if anonymous scan rate limits become a problem.
3. Discover `main`, normal branches and origin pull requests. Do not expose
   credentials to untrusted fork PRs.
4. Script Path = `Jenkinsfile`.
5. Add the `docker-linux` label to the intended Jenkins agent.
6. Set Jenkins Location URL to `https://jenkins.solars.io.vn/`; port `8080`
   remains loopback-only.
7. In GitHub, add webhook `https://jenkins.solars.io.vn/github-webhook/`, content
   type JSON, secret enabled, events Push and Pull request. Restrict Jenkins port
   `8080` so it is never directly public.

### Configure `solar-ai-production`

1. New Item → Pipeline → name exactly `solar-ai-production`.
2. Definition = Pipeline script, not Pipeline script from SCM.
3. Review and paste `deploy/jenkins/production.Jenkinsfile.example`.
4. Ensure the Lockable Resources plugin can create/use `solar-r3-ai-prod`.
5. Restrict configure/build permissions to administrators and the CI service
   identity. Do not allow anonymous/manual arbitrary parameters.
6. Run a credential/SSH preflight before the first real merge.

The trusted job independently checks that `GIT_SHA` is exactly the current
`origin/main`, rebuilds and rescans it, pushes the full-SHA tag, resolves the
registry digest, signs the digest, verifies the signature, transfers only the
deployment payload and invokes the VPS deploy script through loopback SSH. R3
again enforces its repository allowlist and Cosign signature before pulling.

## 9. Branch and release flow

The repository's current development branch is `dev`, while deployment is
triggered only by `main`:

```text
deploy/jenkins -> dev -> reviewed PR -> main -> solar-ai-ci -> solar-ai-production
```

A push to `deploy/jenkins` runs CI only if the Multibranch job discovers normal
branches. It does not deploy production. A merge/push to `main` deploys only
after every gate succeeds. Protect `main`: require review and CI, block direct
pushes and force-pushes, and keep only administrators able to change Jenkins
production credentials/job scripts.

## 10. Acceptance checks and rollback

From an external client, run:

```bash
curl --fail --show-error --silent https://ai.solaris.io.vn/live
curl --fail --show-error --silent https://ai.solaris.io.vn/ready
openssl s_client -connect ai.solaris.io.vn:443 \
  -servername ai.solaris.io.vn -alpn h2 </dev/null 2>/dev/null \
  | openssl x509 -noout -subject -issuer -ext subjectAltName
grpcurl -import-path . -proto protos/ai_service.proto \
  -d '{}' ai.solaris.io.vn:443 aimodule.v1.AiService/Health
```

Also verify on R3:

```bash
cd /opt/solar-ai/current
docker compose --project-name solar-ai \
  --env-file /opt/solar-ai/config/host.env \
  --env-file deploy.env -f docker-compose.prod.yml ps
docker logs --since 10m solar-ai-module
sudo systemctl status caddy --no-pager --full
sudo journalctl -u caddy --since '10 minutes ago' --no-pager
```

After a Backend/observability VPS is later provisioned, confirm BatteryService
has no TLS/gRPC errors, force one real prediction, check all Prometheus targets,
and confirm AI logs arrive in Loki. These are not blockers for the initial
R3-only release. Host Caddy access logs remain in the systemd journal on R3.

The deploy and rollback scripts repeat the checks for the selected mode. In
standalone mode the helper verifies container health and that public metrics are
forbidden. In central mode it additionally sends a unique request through host
Caddy and queries the AI access-log marker back from Loki:

```bash
/opt/solar-ai/current/deploy/scripts/verify-observability.sh
```

From an Internet client, `https://ai.solaris.io.vn/metrics/` must return `403`.
From R4 with `--resolve ai.solaris.io.vn:443:10.20.0.2`, it must return
Prometheus text with a valid certificate for `ai.solaris.io.vn`.

Manual rollback uses the previous immutable release:

```bash
/opt/solar-ai/current/deploy/scripts/rollback.sh
```

The rollback script verifies the old image digest/signature and repeats direct
plus TLS ingress smoke tests before moving `current`.

## 11. Backups and operations

- Back up `/opt/solar-ai/data` and host Caddy state daily to encrypted off-VPS
  storage. Test restore regularly.
- Alert on `/ready`, restart loops, model/RAG errors, TLS expiry, p95 inference,
  HTTP/gRPC error rate, memory pressure, disk below 15%, and missing Prometheus
  or Loki targets.
- Add OpenTelemetry trace export to Backend Tempo and propagate W3C
  `traceparent` over both gRPC and HTTPS before treating distributed tracing as
  complete. Metrics and logs are centralized by this release; tracing is a
  separate hardening milestone.
- Keep at least current and previous releases/images. Prune older data only in a
  reviewed maintenance job outside deployments.
- Never commit `.env`, provider keys, registry tokens, SSH keys or the Cosign
  private key.
- One Uvicorn worker is intentional because every worker would load another full
  model set. Scale vertically first.
