# Quick start

Two paths to a running Morpheus: on your laptop to try it, on your own server to sell with it.

## 1. On your laptop (about 15 minutes)

You need **Python 3.12** and **Redis** (`brew install redis && brew services start redis` on a
Mac, `sudo apt install redis-server` on Ubuntu). Without Redis every queued task retries its
connection 20 times, so pages still load but anything that queues work, the demo seed included, stalls.

```bash
git clone https://github.com/magnetoid/Morpheus.git
cd Morpheus
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.lock.txt
printf 'DEBUG=True\nDATABASE_URL=sqlite:///db.sqlite3\nMORPHEUS_EXTRA_APPS=plugins.installed.demo_data\n' > .env
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Measured on a Mac on 2026-11-10: the install took about 3 minutes and the first `migrate`
about 4½. Open `http://127.0.0.1:8000/dashboard/` and sign in with the email and password
you gave `createsuperuser` (the email is the sign-in name). Then either:

- `python manage.py morph_seed_demo` loads a sample bookshop (50 books, genres, collections,
  vendors, customers) in under a minute; or
- add an AI key under Settings → AI and describe your store in one sentence at
  `/dashboard/apps/store_bootstrap/start/`.

SQLite skips pgvector, so semantic search falls back to keywords. `CELERY_TASK_ALWAYS_EAGER`
is on **only** under the test suite (`settings._RUNNING_TESTS`), so a queued task
(`.delay(...)`) waits in Redis until a worker runs: `celery -A morph worker`.

Don't copy `.env.example` for this: it is a template for a production server and points the
database at a Postgres host you would have to fill in.

## 2. On your own server, with Coolify

```text
+ New Resource → Docker Compose
  Repo:         https://github.com/magnetoid/morpheus
  Compose file: docker-compose.yml
  Env vars:     paste from .env.coolify.example
  Domain:       bind your.domain.com to the `web` service
```

`docker-compose.yml` is written for Coolify and ships **web + worker + beat + postgres + redis
+ pgbouncer** wired through Coolify's magic variables (`SERVICE_FQDN_WEB`,
`SERVICE_PASSWORD_POSTGRES`, `SERVICE_PASSWORD_REDIS`). Outside Coolify those variables are
empty and no port is published, so `docker compose up` on a laptop does not give you a
working store. The web container waits for the database, backs it up and migrates
(`manage.py safe_migrate`), then starts gunicorn. Create the first staff account with
`python manage.py createsuperuser` in the web container's terminal.

The five live stores run this way. Step by step: [`docs/deploy-coolify.md`](deploy-coolify.md).

## What you get on first boot

- Storefront at `/`
- Staff dashboard at `/dashboard/`, with help for every app at `/dashboard/help/`
- MCP cluster at `/mcp/{storefront,cart,checkout,admin}/v1/`
- UCP manifest at `/.well-known/ucp.json`
- Agent acceptance manifest at `/.well-known/agent.json`
- Sitemap, robots and LLM hints at `/sitemap.xml`, `/robots.txt`, `/llms.txt`

## Connect ChatGPT / Claude Desktop

See [`docs/AGENT_PROTOCOLS.md`](AGENT_PROTOCOLS.md) for client configuration snippets.
