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

## Detailed capture and handing errors to Claude Code

- **Turn it on** from Settings → Developer → Errors: *Turn on for 24 hours* or
  *7 days*. It switches itself off at the end time. While on, the store also
  records warnings, rejected requests (400/403/405/429), broken internal links,
  responses slower than 3 seconds, Celery task retries, and in browsers console
  errors, failed requests and missing images or scripts, each with its request.
  Turning it on or off is audited.
- **Hand the errors to Claude Code:** *Copy for Claude Code* on the page (or
  *Download report*) gives one Markdown report of the open groups, errors first,
  with tracebacks, request context and what to do. From a shell on the host:

  ```bash
  docker exec <web container> python manage.py errors_report            # Markdown, last 7 days
  docker exec <web container> python manage.py errors_report --days 30 --json
  docker exec <web container> python manage.py errors_report --resolve <fingerprint>
  ```

  Agents with `diagnostics.read` read the same through `errors.recent` and
  `errors.get` over MCP.
- **Resolve** a group once its fix is live (*Mark resolved* on its page, or
  `--resolve`). A resolved group that fires again shows as *Back again*.

## Rollback

- Code: automatic since v0.121.0 for a store that a push leaves down. deploy-smoke's
  guard puts it back on the previous release, the run stays red, and the store emails
  the operators. A rollback to a release older than v0.121.0 cannot email; the red run
  is the signal. Do not click Redeploy in Coolify afterwards: it builds `main`, the
  failed commit. Push a fix, or `git revert` the bad commit and push; that push deploys
  every store again. By hand: the same revert-and-push, verified with deploy-smoke.
- Schema: migrations are not auto-reversed. Since v0.118.0, every deploy that
  migrates first backs the database up to `/app/backups/pre-deploy/`, named
  after the version it was taken before, and stops before migrating if that
  backup fails. If a migration crashed mid-apply, restore that backup (see
  Backups), then redeploy the last good commit.

## Backups

- **Nightly** (the backups app, 03:30 UTC): database and media to
  `/app/backups/morpheus-backup-<UTC>.tar.gz`, seven kept.
- **Before each deploy that migrates** (`manage.py safe_migrate`, v0.118.0): the
  database alone to `/app/backups/pre-deploy/morpheus-backup-<UTC>-<version>-<commit>.tar.gz`,
  five kept. `DeployEvent` rows say which deploy took which.
- Both live on the store's `backup_data` volume, which the web and worker
  containers mount, **on the same host as the store**. They are not off-site.
- **Rehearse a restore** into a scratch database; it never touches the store's
  data. A backup that has never been restored is a guess, not a plan. In the
  store's web container, run
  `docker exec -i <web> python manage.py shell < this snippet`:

  ```python
  import os, subprocess, tarfile, tempfile
  from django.conf import settings
  from django.db import connection
  from core.models import DeployEvent

  db = settings.DATABASES['default']
  env = dict(os.environ, PGPASSWORD=db['PASSWORD'])
  conn = ['-h', db['HOST'], '-p', str(db['PORT'] or 5432), '-U', db['USER']]
  backup = DeployEvent.objects.exclude(backup='').first().backup
  with tempfile.TemporaryDirectory() as tmp:
      with tarfile.open(backup) as tar:
          tar.extract('db.dump', tmp, filter='data')
      subprocess.run(['createdb', *conn, 'restore_check'], env=env, check=True)
      try:
          restored = subprocess.run(['pg_restore', *conn, '-d', 'restore_check', '--no-owner', f'{tmp}/db.dump'], env=env, capture_output=True, text=True)
          print('RESTORE pg_restore exit', restored.returncode, restored.stderr[-400:])
          copy = subprocess.run(['psql', *conn, '-d', 'restore_check', '-tAc', 'select count(*) from catalog_product'], env=env, check=True, capture_output=True, text=True).stdout.strip()
          with connection.cursor() as cur:
              cur.execute('select count(*) from catalog_product')
              print('RESTORE products in the copy', copy, '| live', cur.fetchone()[0])
      finally:
          subprocess.run(['dropdb', *conn, 'restore_check'], env=env, check=True)
          print('RESTORE scratch database dropped')
  ```
- **Restoring** (v0.120.0) puts the whole database back as a backup has it, all or
  nothing: the dump is rendered to SQL and run in one transaction after the `public`
  schema is emptied. It first backs the current data up into `/app/backups/pre-restore/`
  (pruned only after a restore that worked: ten kept, never the one just restored), so a
  restore can be undone the same way. A superuser starts it from Settings → Version &
  updates → Backups → Restore…, which says what will be replaced and which migrations the
  backup lacks, and asks for the store's name. From a shell:
  `docker exec -it <web> python manage.py morph_restore /app/backups/pre-deploy/<file> --confirm "<store name>" --reload-web 1`.
  `--reload-web 1` reloads the web workers, because gunicorn is PID 1 in the web container.
  - While it runs, every page answers 503 "restoring" (`/healthz` excepted).
  - Access comes back as it was: API tokens, staff accounts, passwords and two-factor
    devices revoked since the backup work again. Revoke them again afterwards.
  - It never runs migrations. A backup older than the running code lacks some, and parts
    of the store fail until they run. A redeploy, or a restart of the web container
    (`safe_migrate`), runs them. If one of them is why you restored, put the previous
    version back first.
  - Afterwards, restart the worker and beat (Coolify → Restart), so background jobs read
    the restored data.
  - The outcome, a refusal included, is in `/app/backups/restore/last.json`, and the
    output of a screen-started restore is in `restore.log` beside it.
  - A restore that is killed (a deploy replaced the container) stops closing the store 90 s
    later. It changed everything or nothing.

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
