# AI Module production deployment

This is the source of truth for deploying `GSU26SE55/ai-module` to the dedicated
Ubuntu DigitalOcean VPS. Backend and IoT run on VPS1; AI runs on VPS2 with
Docker Compose. A successful, non-PR Jenkins build of `main` is the only event
that may request a production deployment.

## 1. Production contract

VPS2 runs five containers in the `solar-ai` Compose project:

| Container | Purpose | Exposure |
|---|---|---|
| `solar-ai-caddy` | ACME certificate, TLS termination, gRPC/REST routing | public TCP `80`, TCP `443` |
| `solar-ai-module` | FastAPI, gRPC, NASA/LFP models, embedded ChromaDB/RAG | Docker network only: `8000`, `50051` |
| `solar-ai-node-exporter` | VPS CPU/RAM/disk metrics | WireGuard only: `9100` |
| `solar-ai-cadvisor` | Container metrics | WireGuard only: `8082` |
| `solar-ai-alloy` | Docker log shipping | outbound to Loki on VPS1 |

Both backend transports use the same origin:

- primary gRPC: `https://ai.solars.io.vn:443` over HTTP/2;
- fallback REST: `https://ai.solars.io.vn`;
- Caddy routes gRPC to `ai-module:50051` using h2c and all other HTTPS traffic
  to FastAPI on `ai-module:8000`.

Ports `8000` and `50051` are not published on the VPS. ChromaDB is embedded in
the AI process rather than deployed as another container. The immutable image
contains a checksum-verified knowledge-base seed; mutable KB, history and
feedback state live under `/opt/solar-ai/data`.

## 2. Blocking DNS check

The intended record is:

```text
ai.solars.io.vn.  A  168.144.48.16
```

Replace `168.144.48.16` everywhere below if that is not the actual public IPv4
shown on the AI Droplet. Do not add an AAAA record unless IPv6 is configured on
VPS2, Caddy listens on it and the firewall also permits it.

At the follow-up audit on **2026-08-13**, all four authoritative nameservers
returned the intended Reserved IPv4:

```text
ns1.zonedns.vn -> 168.144.48.16
ns2.zonedns.vn -> 168.144.48.16
ns3.zonedns.vn -> 168.144.48.16
ns4.zonedns.vn -> 168.144.48.16
```

The AAAA result was empty. DNS was ready at that audit, but it remains a
deployment-time invariant rather than a one-time assumption. Verify from any
Internet-connected machine before the first release and after every IP change:

```bash
dig +short NS solars.io.vn
for ns in ns1.zonedns.vn ns2.zonedns.vn ns3.zonedns.vn ns4.zonedns.vn; do
  dig +short "@${ns}" A ai.solars.io.vn
done
dig +short AAAA ai.solars.io.vn
```

The four A answers must be identical to VPS2 and the AAAA result must be empty.
The deployment preflight repeats these authoritative checks. It accepts
`AI_PUBLIC_IPV4` only when the address is assigned locally or DigitalOcean's
link-local metadata service reports the exact address as the active Reserved
IPv4 for this Droplet. It refuses to touch the running release when these checks
fail.

## 3. VPS2 capacity and base packages

Use Ubuntu 24.04 LTS x86_64, 4 vCPU, 8 GiB RAM and at least 80 GiB SSD. No GPU is
required. The AI container is limited to 3.25 CPU/5 GiB; the other four
containers use separate small limits. Preflight requires at least 10 GiB free
disk and 2 GiB currently available RAM. Do not colocate Jenkins, PostgreSQL,
RabbitMQ, Redis, MinIO, Prometheus or Grafana on this VPS.

Before provisioning, take a DigitalOcean snapshot. Then install base tools:

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

Install Cosign on VPS2 and the Jenkins Docker agent from the official Sigstore
release, then confirm `cosign version`. Keep the same reviewed major/minor
version on both hosts.

## 4. Network and DigitalOcean firewall

Use a DigitalOcean Cloud Firewall. Docker-published ports can bypass ordinary
UFW forwarding rules, so UFW alone is not the production security boundary.

Inbound rules for the AI Droplet:

| Protocol/port | Source | Reason |
|---|---|---|
| TCP 22 | Jenkins VPS public IP and approved admin IP only | deployment/administration |
| TCP 80 | all IPv4 | forced ACME HTTP-01 and HTTP-to-HTTPS redirect |
| TCP 443 | backend VPS public IP; add an admin test IP only temporarily | gRPC + HTTPS fallback |
| UDP WireGuard port, e.g. 51820 | backend VPS public IP | private monitoring/log network |

Do not create public rules for `8000`, `50051`, `8082` or `9100`. The Caddy
configuration disables TLS-ALPN challenges so certificate renewal needs public
port 80, while application port 443 can remain source-allowlisted. The backend
and AI Droplets should use stable/reserved public IPs; update the firewall before
changing either one.

For central Prometheus/Loki, configure WireGuard as `10.20.0.1/24` on VPS1 and
`10.20.0.2/24` on VPS2. Allow VPS1 to scrape only:

- `https://ai.solars.io.vn/metrics` for application HTTP/gRPC metrics;
- `10.20.0.2:9100/metrics` for node-exporter;
- `10.20.0.2:8082/metrics` for cAdvisor.

Alloy pushes logs to `http://10.20.0.1:3100/loki/api/v1/push`. If WireGuard is
not ready, bind monitoring to `127.0.0.1` temporarily, but Prometheus on VPS1
will not have complete host/container monitoring; that is not production-ready.

## 5. One-time VPS2 provisioning

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
  /opt/solar-ai/data/classification-feedback \
  /opt/solar-ai/data/caddy/data \
  /opt/solar-ai/data/caddy/config
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
│   ├── caddy/{data,config}/
│   ├── kb/
│   ├── prescription-history/
│   └── classification-feedback/
├── incoming/
└── releases/
```

Create `/opt/solar-ai/config/host.env` from `deploy/host.env.example`:

```dotenv
AI_PUBLIC_DOMAIN=ai.solars.io.vn
AI_DNS_ZONE=solars.io.vn
AI_PUBLIC_IPV4=168.144.48.16
ACME_EMAIL=YOUR_MONITORED_EMAIL
AI_MONITORING_BIND_IP=10.20.0.2
AI_SECRETS_FILE=/opt/solar-ai/secrets/ai.env
LOKI_PUSH_URL=http://10.20.0.1:3100/loki/api/v1/push
```

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
`/opt/solar-ai/config/cosign.pub`. Never copy the private key to VPS2. Log in to
GHCR once as `deploy` with a read-only robot/PAT so Compose can pull images:

```bash
printf '%s' 'READ_ONLY_GHCR_TOKEN' | docker login ghcr.io \
  --username 'ROBOT_OR_GITHUB_USER' --password-stdin
```

Delete the token from shell history if it was entered interactively. Prefer a
short-lived secret passed through a protected terminal rather than a literal as
shown in the placeholder.

## 6. Caddy TLS and automatic verification

`deploy/caddy/Caddyfile` obtains and renews a publicly trusted certificate,
redirects port 80 to HTTPS and routes both transports. Certificate/account state
is persistent in `/opt/solar-ai/data/caddy`; include it in backups.

Deployment succeeds only after all of the following pass:

1. all model/RAG artifact checksums;
2. direct `/live`, `/ready` and real REST inference;
3. direct standard/custom gRPC health plus NASA and LFP inference;
4. the same REST and gRPC tests through Caddy with the real certificate name;
5. Compose health for all containers.

The TLS smoke runs inside the Docker network using the production FQDN as a
network alias. It therefore validates certificate hostname, TLS trust, HTTP/2
and Caddy routing without depending on public hairpin routing. Failure triggers
automatic rollback to the previous immutable release.

## 7. Backend production settings

The existing backend client code supports this topology. BatteryService uses
gRPC primary plus HTTP fallback, while TicketService uses gRPC. However, the
current backend Helm chart does **not** yet define any `Ai__*`/`TicketAi__*`
entries in `deploy/helm/solar-battery/values-vps-small.yaml`. Its deployments
load `solar-config` with `envFrom`, so omitting the keys silently leaves the
application defaults pointing to the obsolete in-cluster AI names.

For the intended k3s deployment, add this map to the backend production values
overlay that Jenkins passes to `helm upgrade` (for the current small-VPS setup,
merge it into the existing `config:` map in `values-vps-small.yaml`):

```yaml
config:
  Ai__Enabled: "true"
  Ai__GrpcAddress: "https://ai.solars.io.vn"
  Ai__HttpBaseUrl: "https://ai.solars.io.vn"
  Ai__TimeoutSeconds: "5"
  Ai__IntervalMinutes: "5"
  Ai__MinReadings: "30"
  Ai__MaxScanReadings: "60"
  Ai__PrescriptionEnabled: "true"

  TicketAi__Enabled: "true"
  TicketAi__BatteryServiceBaseUrl: "http://batteryservice:80"
  TicketAi__AiGrpcAddress: "https://ai.solars.io.vn"
  TicketAi__BatteryGrpcAddress: "http://batteryservice:8081"
  TicketAi__TimeoutSeconds: "5"
  TicketAi__MaxDuplicateCandidates: "10"
```

The current Helm BatteryService only publishes an HTTP service port. Before
enabling TicketService's internal `BatteryGrpcAddress`, its chart must also
publish the BatteryService gRPC listener/Service port expected by the backend
code; that is a separate backend-chart gap, not an AI ingress gap. It does not
affect BatteryService calling AI, but it affects the ticket sensor-verification
path.

Render the backend chart and inspect the generated ConfigMap before upgrading:

```bash
helm template solar-backend deploy/helm/solar-battery \
  -f deploy/helm/solar-battery/values.yaml \
  -f deploy/helm/solar-battery/values-vps-small.yaml \
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
same ASP.NET nested keys in VPS1 `/opt/solar/.env.prod`; the production Compose
loads them through `env_file` and does not translate the short `AI_*` aliases
used by the development Compose:

```dotenv
Ai__Enabled=true
Ai__GrpcAddress=https://ai.solars.io.vn
Ai__HttpBaseUrl=https://ai.solars.io.vn
Ai__TimeoutSeconds=5
Ai__IntervalMinutes=5
Ai__MinReadings=30
Ai__MaxScanReadings=60
Ai__PrescriptionEnabled=true

TicketAi__Enabled=true
TicketAi__BatteryServiceBaseUrl=http://batteryservice:8080
TicketAi__AiGrpcAddress=https://ai.solars.io.vn
TicketAi__BatteryGrpcAddress=http://batteryservice:8081
TicketAi__TimeoutSeconds=5
TicketAi__MaxDuplicateCandidates=10
```

Do not append `/api` or a method path. For gRPC, .NET selects HTTP/2/TLS from
the `https://` URI. For REST fallback, typed HttpClient appends the existing
FastAPI paths. Restart BatteryService and TicketService only after AI TLS smoke
passes.

Because the current backend does not send an API token or mTLS client
certificate, do not add Caddy Basic Auth to these routes. Restrict TCP 443 by
DigitalOcean source IP instead. A future mTLS/shared-token design must update
both backend clients and AI ingress atomically.

## 8. Jenkins architecture

Use two jobs:

1. `solar-ai-ci`: Multibranch Pipeline loaded from repository `Jenkinsfile`.
   It receives no registry-write, Cosign-private or VPS credentials. PRs and
   branches run checks only. A non-PR `main` build requests job 2.
2. `solar-ai-production`: centrally managed Pipeline with the reviewed content
   of `deploy/jenkins/production.Jenkinsfile.example`. Its script is pasted into
   Jenkins rather than loaded from a PR-controlled workspace.

The Docker Linux agent labeled `docker-linux` needs Python 3.11 + venv, Docker
Engine/Compose/Buildx, Git, ShellCheck, Trivy, Syft, Cosign, tar and OpenSSH. Do
not mount the host Docker socket into an Internet-facing Jenkins controller.
Prefer an SSH-connected agent with an isolated workspace. If the Jenkins VPS is
both controller and agent for a student deployment, restrict it by firewall and
understand that Docker access is root-equivalent.

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
| `ai-github-read` | Username/password | GitHub user + fine-grained read token |
| `ai-registry-host` | Secret text | `ghcr.io` |
| `ai-image-repository` | Secret text | `ghcr.io/gsu26se55/ai-module` |
| `ai-registry-write` | Username/password | GHCR push-capable robot/user token |
| `ai-cosign-private-key` | Secret file | encrypted Cosign private key |
| `ai-cosign-public-key` | Secret file | matching public key |
| `ai-cosign-password` | Secret text | Cosign key password |
| `ai-vps2-target` | Secret text | `deploy@168.144.48.16` (or actual VPS2 IP) |
| `ai-vps2-ssh` | SSH username/private key | user `deploy`, dedicated key |
| `ai-vps2-known-hosts` | Secret file | pinned `ssh-keyscan` result verified out-of-band |

Never build `known_hosts` with `StrictHostKeyChecking=no`. From a trusted admin
machine, compare VPS2's `/etc/ssh/ssh_host_ed25519_key.pub` fingerprint with the
scan before uploading it to Jenkins.

### Configure `solar-ai-ci`

1. New Item → Multibranch Pipeline → name `solar-ai-ci`.
2. Add GitHub branch source for `GSU26SE55/ai-module` with `ai-github-read`.
3. Discover `main`, normal branches and origin pull requests. Do not expose
   credentials to untrusted fork PRs.
4. Script Path = `Jenkinsfile`.
5. Add the `docker-linux` label to the intended Jenkins agent.
6. Set Jenkins Location URL to a public **HTTPS** Jenkins domain. The screenshot
   URL `http://188.166.254.92:8080` is not acceptable for production credentials.
7. In GitHub, add webhook `https://JENKINS_DOMAIN/github-webhook/`, content type
   JSON, secret enabled, events Push and Pull request. Restrict Jenkins port 8080
   so it is not directly public after the reverse proxy is active.

### Configure `solar-ai-production`

1. New Item → Pipeline → name exactly `solar-ai-production`.
2. Definition = Pipeline script, not Pipeline script from SCM.
3. Review and paste `deploy/jenkins/production.Jenkinsfile.example`.
4. Ensure the Lockable Resources plugin can create/use `solar-vps2-prod`.
5. Restrict configure/build permissions to administrators and the CI service
   identity. Do not allow anonymous/manual arbitrary parameters.
6. Run a credential/SSH preflight before the first real merge.

The trusted job independently checks that `GIT_SHA` is exactly the current
`origin/main`, rebuilds and rescans it, pushes the full-SHA tag, resolves the
registry digest, signs the digest, verifies the signature, transfers only the
deployment payload and invokes the VPS deploy script. VPS2 again enforces its
repository allowlist and Cosign signature before pulling.

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

Temporarily allow the admin test IP on TCP 443, then run:

```bash
curl --fail --show-error --silent https://ai.solars.io.vn/live
curl --fail --show-error --silent https://ai.solars.io.vn/ready
openssl s_client -connect ai.solars.io.vn:443 \
  -servername ai.solars.io.vn -alpn h2 </dev/null 2>/dev/null \
  | openssl x509 -noout -subject -issuer -ext subjectAltName
grpcurl -import-path . -proto protos/ai_service.proto \
  -d '{}' ai.solars.io.vn:443 aimodule.v1.AiService/Health
```

Also verify on VPS2:

```bash
cd /opt/solar-ai/current
docker compose --project-name solar-ai \
  --env-file /opt/solar-ai/config/host.env \
  --env-file deploy.env -f docker-compose.prod.yml ps
docker logs --since 10m solar-ai-caddy
docker logs --since 10m solar-ai-module
```

On VPS1, confirm BatteryService has no TLS/gRPC errors, force one real
prediction, verify an HTTP fallback with gRPC deliberately blocked in a planned
maintenance test, check all Prometheus targets, and confirm Caddy/AI logs arrive
in Loki.

Manual rollback uses the previous immutable release:

```bash
/opt/solar-ai/current/deploy/scripts/rollback.sh
```

The rollback script verifies the old image digest/signature and repeats direct
plus TLS ingress smoke tests before moving `current`.

## 11. Backups and operations

- Back up `/opt/solar-ai/data` daily to encrypted off-VPS storage, including
  Caddy certificate state. Test restore regularly.
- Alert on `/ready`, restart loops, model/RAG errors, TLS expiry, p95 inference,
  HTTP/gRPC error rate, memory pressure, disk below 15%, and missing Prometheus
  or Loki targets.
- Keep at least current and previous releases/images. Prune older data only in a
  reviewed maintenance job outside deployments.
- Never commit `.env`, provider keys, registry tokens, SSH keys or the Cosign
  private key.
- One Uvicorn worker is intentional because every worker would load another full
  model set. Scale vertically first.
