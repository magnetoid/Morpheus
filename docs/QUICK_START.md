# Quick start

Three paths to a running Morpheus instance, fastest first.

## 1. One-command Coolify deploy

```text
+ New Resource → Docker Compose
  Repo:         https://github.com/magnetoid/morpheus
  Compose file: docker-compose.yml
  Env vars:     paste from .env.coolify.example
  Domain:       bind your.domain.com to the `web` service
```

The default `docker-compose.yml` ships **web + worker + beat +
postgres + redis + pgbouncer** wired through Coolify magic vars
(`SERVICE_FQDN_WEB`, `SERVICE_PASSWORD_POSTGRES`,
`SERVICE_PASSWORD_REDIS`). The web entrypoint waits for the DB,
runs `migrate` + `collectstatic`, then execs gunicorn.

Coolify clicks through to a working storefront in under 5 minutes
on a clean droplet.

Detailed guide: [`docs/deploy-coolify.md`](deploy-coolify.md).

## 2. Plain `docker compose`

```bash
git clone https://github.com/magnetoid/morpheus
cd morpheus
cp .env.example .env       # fill in SECRET_KEY + DOMAIN
docker compose up -d
```

The `web` service auto-migrates on boot. Visit
`http://localhost:8000/dashboard/` and the first signup becomes
the staff superuser.

## 3. Local dev (no Docker)

```bash
git clone https://github.com/magnetoid/morpheus
cd morpheus
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env       # SQLite works out of the box
python manage.py migrate
python manage.py runserver
```

Dev mode runs against SQLite and skips pgvector — semantic search falls
back to keyword. Note `CELERY_TASK_ALWAYS_EAGER` is on **only** under the
test suite (`settings._RUNNING_TESTS`), so locally a queued task
(`.delay(...)`) still needs Redis running to fire. Everything else works.

## What you get on first boot

- Storefront at `/`
- Staff dashboard at `/dashboard/`
- Linda (always-on assistant) at `/dashboard/assistant/`
- MCP cluster at `/mcp/{storefront,cart,checkout,admin}/v1/`
- UCP manifest at `/.well-known/ucp.json`
- Agent acceptance manifest at `/.well-known/agent.json`
- Sitemap + robots + LLM hints at `/sitemap.xml`, `/robots.txt`,
  `/llms.txt`

## Connect ChatGPT / Claude Desktop

See [`docs/AGENT_PROTOCOLS.md`](AGENT_PROTOCOLS.md) for client
configuration snippets.
