# syntax=docker/dockerfile:1.7

# ─── Builder stage ────────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      build-essential \
      libpq-dev \
 && rm -rf /var/lib/apt/lists/*

# The image installs the SAME hashed lock CI tests (requirements.lock.txt);
# requirements.txt holds the floors `uv pip compile` resolves from. Installing
# the floors here meant production floated to whatever PyPI had that day — 48 of
# 107 packages differed from the lock on 2026-10-10 — and a separate
# `gunicorn==23.0.0` pin contradicted the lock. A new dependency goes into
# requirements.txt AND the lock is regenerated in the same commit
# (`uv pip compile requirements.txt -o requirements.lock.txt --generate-hashes --universal`),
# or this build fails on the missing hash.
COPY requirements.lock.txt /app/requirements.lock.txt
RUN pip install --upgrade pip \
 && pip install --require-hashes -r /app/requirements.lock.txt


# ─── Runtime stage ────────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=morph.settings \
    PORT=8000 \
    GUNICORN_WORKERS=4 \
    GUNICORN_TIMEOUT=60

WORKDIR /app

# postgresql-client-16 (for pg_dump used by the nightly backup task) is NOT in
# Debian bookworm's default repos — it ships client-15, and pg_dump 15 REFUSES to
# dump a server 16 (our postgres:16). Add the PGDG apt repo to get a matching
# client. Without pg_dump the backup task throws FileNotFoundError on every run.
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      libpq5 \
      curl \
      ca-certificates \
      gnupg \
 && install -d /usr/share/postgresql-common/pgdg \
 && curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc \
      -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc \
 && echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc] https://apt.postgresql.org/pub/repos/apt bookworm-pgdg main" \
      > /etc/apt/sources.list.d/pgdg.list \
 && apt-get update \
 && apt-get install -y --no-install-recommends postgresql-client-16 \
 && rm -rf /var/lib/apt/lists/* \
 && groupadd --system morpheus \
 && useradd --system --gid morpheus --home-dir /app --no-create-home morpheus

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Janus is the store agent (Linda is brand only). Always install into an
# isolated venv so Django and Janus do not share `plugins/` / `tools/` on
# sys.path. ARG LINDA_JANUS is ignored (kept so old Coolify build-args still
# parse). JANUS_REF is PINNED to a reviewed commit (the owner updates Janus
# occasionally; bump the ARG to move) — and because this layer runs before
# `COPY . /app`, it is cached across pushes instead of rebuilt (216 MB) on
# every deploy. Only the contract file is copied in first: it runs standalone
# under Janus's own interpreter. A running store keeps up between deploys by
# itself when the merchant turns that on (core/assistant/janus_runtime.py).
# ddgs + primp are Linda's free web search backend (pinned in
# janus_runtime.PINS too). The [mcp] extra is load-bearing: without the `mcp`
# package Janus's MCP client silently does nothing and Linda has no store
# tools at all (shipped that way in v0.63.0).
# Every build checks Janus against Morpheus's contract
# (core/assistant/janus_contract.py: the toolsets, config keys, env vars, CLI
# options and state columns the integration relies on, mcp included). When the
# pinned Janus breaks it, the build installs JANUS_KNOWN_GOOD instead, so an
# image never ships an engine Linda cannot use. The report stays at
# /opt/janus/morpheus-contract.json for Settings → AI → Janus.
ARG LINDA_JANUS=1
ARG JANUS_REF=eafb7aba34db8645401ce285edf987054c5d37d5
ARG JANUS_KNOWN_GOOD=eafb7aba34db8645401ce285edf987054c5d37d5
ARG JANUS_REPO=https://github.com/magnetoid/Janus-Agent.git
COPY core/assistant/janus_contract.py /app/core/assistant/janus_contract.py
RUN apt-get update \
 && apt-get install -y --no-install-recommends git \
 && python -m venv /opt/janus \
 && /opt/janus/bin/pip install --upgrade pip \
 && /opt/janus/bin/pip install --no-cache-dir \
      "janus-agent[mcp] @ git+${JANUS_REPO}@${JANUS_REF}" ddgs==9.16.0 primp==2.0.1 \
 && if ! /opt/janus/bin/python -I /app/core/assistant/janus_contract.py > /opt/janus/morpheus-contract.json; then \
      echo "Janus ${JANUS_REF} breaks the Morpheus contract; installing ${JANUS_KNOWN_GOOD}" >&2; \
      cat /opt/janus/morpheus-contract.json >&2; \
      /opt/janus/bin/pip install --no-cache-dir --force-reinstall \
        "janus-agent[mcp] @ git+${JANUS_REPO}@${JANUS_KNOWN_GOOD}" ddgs==9.16.0 primp==2.0.1 \
      && /opt/janus/bin/python -I /app/core/assistant/janus_contract.py > /opt/janus/morpheus-contract.json; \
    fi \
 && ln -sf /opt/janus/bin/janus /usr/local/bin/janus \
 && apt-get purge -y git \
 && apt-get autoremove -y \
 && rm -rf /var/lib/apt/lists/*

COPY --chown=morpheus:morpheus . /app

# The worker mounts its persistent backup volume here (docker-compose
# `backup_data`), and web and worker mount the media volume at /app/media
# (`media_data`). Docker creates a missing mount point as root:root and the app
# runs as morpheus, so every nightly backup failed with PermissionError, and on
# a store created later every upload did (beta.irvingsurvival.com, 2026-10-09;
# /media/ is in .dockerignore, so the image had no /app/media at all). An empty
# named volume takes the ownership of the directory it is first mounted on.
RUN mkdir -p /app/backups /app/media \
 && chown morpheus:morpheus /app/backups /app/media

# Ensure the entrypoint is executable inside the image even if the host bit was lost.
RUN chmod +x /app/scripts/docker-entrypoint.sh

# Bake collected static into the image so admin + dashboard CSS/JS exist
# even when the staticfiles volume is empty/unwritable. SECRET_KEY/DB are
# not needed for collectstatic; pass placeholders to satisfy settings.py.
RUN SECRET_KEY=build-only \
    ALLOWED_HOSTS=localhost \
    CORS_ALLOWED_ORIGINS=http://localhost \
    DATABASE_URL=sqlite:///:memory: \
    DEBUG=False \
    python manage.py collectstatic --noinput

USER morpheus
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD curl -fsS http://localhost:${PORT}/healthz || exit 1

ENTRYPOINT ["/app/scripts/docker-entrypoint.sh"]
CMD ["web"]
