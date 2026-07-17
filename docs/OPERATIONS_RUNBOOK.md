# Morpheus — Operations Runbook

## Production topology (dotbooks.store)

- Request chain: Cloudflare (DNS-only) → Plesk nginx vhost on the host
  (`/var/www/vhosts/system/dotbooks.store/conf/vhost_nginx.conf`, proxies to
  `https://127.0.0.1:8445`) → Coolify Traefik → `web` container (gunicorn).
- **Merging to `main` IS a production deploy** — Coolify watches the repo.
  Every deploy bumps `MORPHEUS_VERSION` + adds a `docs/RELEASE_NOTES.md` entry
  (ADR 0032).

## Health and readiness

- `GET /healthz` — liveness (no dependencies).
- `GET /readyz` — readiness (DB + cache) and the running `version`; this is
  the contract for the deploy smoke below.
- `GET /healthz/deep` — DB + cache + plugin registry + agent runtime +
  outbox lag.

## Deploy verification (deploy-smoke)

- `.github/workflows/deploy-smoke.yml` runs on every push to `main`: it polls
  `/readyz` until production reports the pushed `MORPHEUS_VERSION` and
  `status: ok`, then asserts the homepage returns 200 (25-minute budget).
  A red X on the commit means the deploy never converged — a missed webhook,
  a failed build, or a boot error.
- Run manually after any hand deploy: `bash scripts/deploy_smoke.sh`.

## When a deploy doesn't start or is stuck

- List recent builds:
  `GET <coolify>/api/v1/deployments/applications/<app-uuid>?take=6` (Bearer token).
- Webhooks can silently miss — force a fresh build:
  `POST <coolify>/api/v1/deploy?uuid=<app-uuid>&force=true`.
- A build stuck `in_progress` whose logs end with "Gracefully shutting down
  build container" is a **zombie row** — it wedges the app's whole queue.
  Clear it with `POST /api/v1/deployments/<deployment-uuid>/cancel` (older
  Coolify 500s on this endpoint but still flips the status), cancel duplicate
  `queued` rows, then force a fresh deploy. Coolify only auto-starts the next
  queued build from the "previous build finished" hook, so a DB/API-level
  cancel always needs a fresh trigger afterwards.
- Expect a 1–3 minute 503 window while the container swaps; images that build
  native dependencies take several minutes longer. Don't panic-rollback during
  the window — confirm via the deployments API first.

## Error tracking (Sentry)

- Fully wired in `core/sentry.py` (Django + Celery + logging integrations,
  PII scrubbed in `before_send`). It activates the moment `SENTRY_DSN` is set —
  see the Sentry block in `.env.coolify.example`.
- Without a DSN, production 500s reach only stdout JSON logs and the internal
  `core/errors` pipeline — **nobody is paged**.

## Rollback

- Code: `git revert` the bad commit on `main` and push — that push is itself
  the rollback deploy; verify with deploy-smoke.
- Schema: migrations are not auto-reversed. If a migration crashed mid-apply,
  restore the database from backup, then redeploy the last good commit.

## Backups

- Postgres runs in the Coolify stack — keep scheduled dumps enabled in Coolify
  (Database → Backups) and rehearse a restore periodically. A backup that has
  never been restored is a guess, not a plan.

## Local development

- `docker-compose.yml` provides Postgres, Redis, NATS, OpenTelemetry Collector,
  Prometheus, Grafana. Web: `http://localhost:8000/`, GraphQL: `/graphql/`,
  Grafana: `http://localhost:3000/` (admin/admin).
- Traces export via OTLP to the collector; collector exposes Prometheus
  metrics at `:8889`.

## Kubernetes (reference)

- `k8s/` manifests (+ `hpa-web.yaml`, min 2 / max 10 at 60% CPU) support
  cluster deployments. Production currently runs on Coolify (above), not k8s.

## Autonomous Ops (advisory)

- `ops-agent` exposes `GET /recommendations` for policy suggestions; apply via
  GitOps PRs.
