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

COPY requirements.txt /app/requirements.txt
RUN pip install --upgrade pip \
 && pip install -r /app/requirements.txt \
 && pip install gunicorn==23.0.0


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

COPY --chown=morpheus:morpheus . /app

# Optional isolated Janus venv for Linda (subprocess — own sys.path).
# Build with: --build-arg LINDA_JANUS=1
ARG LINDA_JANUS=0
RUN if [ "$LINDA_JANUS" = "1" ]; then \
      apt-get update \
      && apt-get install -y --no-install-recommends git \
      && python -m venv /opt/janus \
      && /opt/janus/bin/pip install --upgrade pip \
      && /opt/janus/bin/pip install --no-cache-dir \
           "janus-agent @ git+https://github.com/magnetoid/janus.git@main" \
      && ln -sf /opt/janus/bin/janus /usr/local/bin/janus \
      && rm -rf /var/lib/apt/lists/* ; \
    fi

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
