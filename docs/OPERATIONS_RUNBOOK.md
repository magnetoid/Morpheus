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
- **A deploy that died after "Removing old containers" leaves the store down**
  (503 "no available server"): the compose-based apps stop the whole stack —
  web, worker, beat, postgres, redis — before starting the new one, so a job
  that dies in between (supernatural, 2026-10-10) leaves nothing running while
  the row still says `in_progress` and the logs simply stop. If the image was
  built (the log shows "Image … Built"), start the stack from the helper
  container's artifacts instead of rebuilding:
  `docker exec <deployment-uuid> sh -c 'cd /artifacts/<deployment-uuid> &&
  docker compose --env-file .env --project-name <app-uuid>
  --project-directory /artifacts/<deployment-uuid> -f docker-compose.yml up -d
  --no-build'` — the helper (`coollabsio/coolify-helper`, named after the
  deployment) has the compose file, the env and the docker socket. Then cancel
  the row (above) so the queue moves; no fresh deploy is needed.

## Launching a store (pre-launch switches)

A store being set up can stay out of search engines and sell nothing that is
not ready, while people can already browse it. Two settings, both off by default:

- **Settings → SEO → "Hide the store from search engines until launch"**
  (`seo.hide_until_launch`): every page is `noindex, nofollow`, the sitemaps
  are empty, robots.txt names no sitemap (crawling stays allowed, so the
  noindex is read), llms.txt / agents.md / the AI feed answer 404 and nothing
  pings IndexNow.
- **Settings → Payments → Checkout & cart → "Products hidden from search are
  pre-launch previews"** (`orders.prelaunch_noindex_not_for_sale`): a product
  marked noindex can be viewed but not added to a cart or ordered — by any path
  (storefront, GraphQL, agents). To put one product on sale, clear its noindex.

On launch day turn both off, then resubmit the sitemap in Search Console. Both
are read fresh on every request, so a change applies to every worker at once.

## Error tracking (Sentry)

- Fully wired in `core/sentry.py` (Django + Celery + logging integrations,
  PII scrubbed in `before_send`). It activates the moment `SENTRY_DSN` is set —
  see the Sentry block in `.env.coolify.example`.
- Without a DSN, production 500s reach stdout JSON logs and the internal
  `core/errors` pipeline (`ErrorEvent`, `/dashboard/errors/`), which survives
  redeploys. Since v0.75.26 that pipeline also emails people (below).

## Error emails and the nightly health check

- **Daily digest** (`core.errors.tasks.error_digest_task`, 06:30 UTC): the last
  24 hours' server errors grouped by cause, most frequent first. Nothing is sent
  on a clean day.
- **Nightly health check** (`core.errors.tasks.nightly_health_check`, 05:00 UTC):
  core checks that outgoing email is set up and the order-email templates load.
  Each app adds its own through the `HEALTH_CHECKS` filter: payments (a payment
  method is offered), orders (a real product can be carted and priced — rolled
  back), storefront (home, a product, cart and checkout load through the CDN),
  booking_marketplace (listings and an experience page). A failure is recorded
  as an `ErrorEvent` (`HealthCheckFailed`) and emailed immediately.
- **Recipients:** `ERROR_ALERT_EMAILS` (comma-separated env) if set, else the
  active superusers, else the store's contact email.
- **Run by hand:** `python manage.py shell -c "from core.errors.health import
  run_checks; print(run_checks())"` (reports only; `run_and_report()` also
  records and emails).
- **An app that can stop the store selling should contribute a check.** A
  release can break checkout in ways no request logs as an error — a payment
  method with no keys, a template no loader finds — and only a check notices.

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
