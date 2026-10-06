# Deploying Morpheus on Coolify

This guide walks through deploying Morpheus to a [Coolify](https://coolify.io)
instance using the default `docker-compose.yml` manifest.

The compose file is intentionally lean: it ships **web + worker + beat +
postgres + redis** and lets Coolify handle TLS, routing, secrets, and storage.

---

## Prerequisites

- A Coolify v4 server with at least 2 GB RAM (4 GB recommended).
- A domain that points to the Coolify server's public IP. You'll bind it to
  the `web` service later.
- Optional: a GHCR / Docker Hub account if you want to deploy a pre-built
  image instead of building from source.

---

## Step 1 — Create the application

1. In Coolify, choose **+ New Resource → Docker Compose**.
2. Source: connect to GitHub and pick `magnetoid/morpheus` (or paste the repo
   URL for any fork). Branch: `main`.
3. **Compose file:** `docker-compose.yml` (this is the default — nothing to change).
4. Save.

Coolify will parse the manifest and detect `web` as the public service.

---

## Step 2 — Configure environment variables

Open **Environment Variables** for the new application. Paste the contents of
[`.env.coolify.example`](../.env.coolify.example), then fill in:

| Variable | Source |
|---|---|
| `SECRET_KEY` | Generate with `python -c 'import secrets; print(secrets.token_urlsafe(64))'` |
| `ALLOWED_HOSTS` | Apex/www/extra hostnames (Coolify's domain is added automatically) |
| `CORS_ALLOWED_ORIGINS` | `https://your-storefront.example.com` |
| `STRIPE_*` | Stripe Dashboard → Developers → API keys / Webhooks |
| `OPENAI_API_KEY` *or* `ANTHROPIC_API_KEY` | Provider dashboard |
| `EMAIL_*` | Your SMTP provider (SendGrid, Postmark, AWS SES, …) |

You **don't** need to set:

- `SERVICE_PASSWORD_POSTGRES`, `SERVICE_PASSWORD_REDIS` — Coolify generates them.
- `SERVICE_FQDN_WEB` — Coolify resolves this from the domain you bind in step 3.
- `DATABASE_URL`, `REDIS_URL` — wired inside the compose using the auto-generated passwords.

---

## Step 3 — Bind the domain

Under **Domains** for the `web` service:

1. Add your domain (e.g. `shop.example.com`).
2. Enable **HTTPS** (Let's Encrypt is automatic).
3. Save. Coolify exposes `web:8000` through its Traefik proxy.

The `ALLOWED_HOSTS` Django setting is built as
`${SERVICE_FQDN_WEB},${ALLOWED_HOSTS}` so the new domain is whitelisted
without touching env vars.

---

## Step 4 — Deploy

Hit **Deploy**. Coolify will:

1. Build the Dockerfile (multi-stage, non-root `morpheus` user, gunicorn).
2. Start `postgres` + `redis` and wait for their healthchecks.
3. Start `web`, which runs `migrate` + `collectstatic` via the entrypoint
   before serving via gunicorn.
4. Start `worker` (Celery) and `beat` (Celery scheduler — runs the
   observability rollups and any plugin-provided periodic tasks).

The web service exposes `/healthz` (liveness) and `/readyz` (DB + cache
checks). Coolify will mark the service healthy once `/healthz` returns 200.

---

## Step 5 — Create a superuser

Open Coolify's **Terminal** for the running `web` container and run:

```bash
python manage.py createsuperuser
```

You can also run it as a one-shot from your laptop:

```bash
ssh root@<coolify-host> "docker exec -it $(docker ps -qf name=morpheus-web-1) \
    python manage.py createsuperuser"
```

---

## Common operations

### Run a one-off migration

The `migrate` mode is supported by the entrypoint; use it for pre-deploy jobs:

```yaml
# In Coolify's "Pre-deployment commands":
docker compose run --rm web migrate
```

### Tail logs

```bash
docker compose -f docker-compose.yml logs -f web worker beat
```

### Scale workers

Set `CELERY_CONCURRENCY` higher in env, or scale the `worker` service replicas
in Coolify (Resources → worker → Replicas).

### Persist media on S3

Set `USE_S3=True` and the `AWS_*` vars. The `media_data` volume becomes a
no-op; uploaded files go to S3 directly.

### Use an external Postgres

If you provision Postgres as a Coolify *Database* resource:

1. Remove the `postgres` service from `docker-compose.yml` (or
   comment it out and the `depends_on` references).
2. Set `DATABASE_URL` to the external connection string.
3. Re-deploy.

The same applies to Redis.

### Add NATS JetStream (optional)

The transactional outbox publisher in `core/tasks.py:process_outbox` defaults
to a Celery-driven loop. To use NATS instead, uncomment the `nats` service in
`docker-compose.yml`, add `NATS_URL=nats://nats:4222` to the env, and
re-deploy.

---

## Health & observability

| Endpoint | Purpose |
|---|---|
| `/healthz` | Liveness — Coolify uses this for the container healthcheck |
| `/readyz` | Readiness — DB + cache reachable; returns 503 when degraded |
| `/v1/products/` | Public REST API (sanity check) |
| `/graphql/` | GraphQL endpoint |

For metrics + traces, point `OTEL_EXPORTER_OTLP_ENDPOINT` at any OTLP HTTP
collector (Grafana Cloud, Honeycomb, Tempo, self-hosted otel-collector).

---

## Troubleshooting

**"DisallowedHost" error on first request**
The hostname Coolify assigned is not in `ALLOWED_HOSTS`. The compose already
appends `${SERVICE_FQDN_WEB}` automatically — make sure the env block in the
Coolify UI has `SECRET_KEY` set (otherwise the app refuses to boot, masking
the underlying error).

**Worker pod restart-loops with "Connection refused: redis"**
The Redis healthcheck failed. Check the Redis container logs — usually a bad
`SERVICE_PASSWORD_REDIS` injection. Re-deploy from a fresh build.

**`makemigrations --check` failing in CI but local is clean**
You committed model changes without running `makemigrations`. Rerun:
```bash
python manage.py makemigrations
```
and commit the resulting migration files.

**`/healthz` returns 200 but `/readyz` returns 503**
DB or cache connection failed. SSH into the container and check
`echo $DATABASE_URL` / `echo $REDIS_URL`, and run:
```bash
python manage.py check --deploy
```
