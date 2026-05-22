#!/usr/bin/env sh
# Morpheus container entrypoint.
# Modes (selected by first arg):
#   web     — wait for DB, migrate, collectstatic, run gunicorn
#   worker  — wait for DB, run celery worker
#   beat    — wait for DB, run celery beat (with django-celery-beat scheduler if present)
#   shell   — exec django shell (for ad-hoc debugging)
#   migrate — run migrations once and exit (useful as a Coolify pre-deploy job)
#   <other> — exec arguments verbatim
set -eu

MODE="${1:-web}"
shift || true

wait_for_db() {
  if [ -z "${DATABASE_URL:-}" ]; then
    echo "[entrypoint] DATABASE_URL not set; skipping DB wait."
    return
  fi
  python - <<'PY' || exit 1
import os, sys, time, urllib.parse
url = urllib.parse.urlparse(os.environ["DATABASE_URL"])
host = url.hostname
port = url.port or 5432
if not host or url.scheme.startswith("sqlite"):
    sys.exit(0)
import socket
deadline = time.time() + 60
while time.time() < deadline:
    try:
        with socket.create_connection((host, port), timeout=2):
            sys.exit(0)
    except OSError:
        time.sleep(1)
print(f"[entrypoint] Timed out waiting for DB at {host}:{port}", file=sys.stderr)
sys.exit(1)
PY
}

run_migrations() {
  echo "[entrypoint] Running migrations…"
  python manage.py migrate --noinput
}

collect_static() {
  # Static is baked into the image at build time (see Dockerfile). This
  # function exists for back-compat callers but is a no-op in the standard
  # build. Set FORCE_COLLECTSTATIC=1 to override.
  if [ "${FORCE_COLLECTSTATIC:-0}" = "1" ]; then
    echo "[entrypoint] Collecting static files (forced)…"
    python manage.py collectstatic --noinput || true
  fi
}

case "$MODE" in
  web)
    wait_for_db
    run_migrations
    collect_static
    # Concurrency model:
    #   Sync workers handle one request at a time → 4 workers = 4
    #   concurrent requests max. That's what was causing
    #   ERR_CONNECTION_RESET under load (slow LLM call holds a worker
    #   for 8s, healthcheck takes one, two browser requests fill the
    #   remaining two → 5th request gets TCP RST).
    #
    # Switching to `gthread` keeps the sync code path (no async refactor
    # of the ORM) but lets each worker juggle multiple requests on
    # threads. With 4 workers × 8 threads = 32 concurrent requests, and
    # plenty of headroom for the LLM-call-blocks-a-worker scenario.
    #
    # max-requests cycles workers periodically to prevent memory leaks
    # on long-running PDF / image processing — workers cycle gracefully
    # one at a time so requests don't drop.
    #
    # graceful-timeout=10 gives in-flight requests a chance to finish
    # during deploy cutover (previously 30s default, sometimes
    # truncated by Docker's SIGKILL).
    exec gunicorn morph.wsgi:application \
        --bind "0.0.0.0:${PORT:-8000}" \
        --worker-class "${GUNICORN_WORKER_CLASS:-gthread}" \
        --workers "${GUNICORN_WORKERS:-4}" \
        --threads "${GUNICORN_THREADS:-8}" \
        --timeout "${GUNICORN_TIMEOUT:-30}" \
        --graceful-timeout "${GUNICORN_GRACEFUL_TIMEOUT:-10}" \
        --keep-alive "${GUNICORN_KEEPALIVE:-5}" \
        --max-requests "${GUNICORN_MAX_REQUESTS:-1000}" \
        --max-requests-jitter "${GUNICORN_MAX_REQUESTS_JITTER:-50}" \
        --access-logfile - \
        --error-logfile -
    ;;
  worker)
    wait_for_db
    exec celery -A morph worker -l "${CELERY_LOG_LEVEL:-info}" \
        --concurrency "${CELERY_CONCURRENCY:-4}"
    ;;
  beat)
    wait_for_db
    # Schedule DB needs a writable path. The non-root `morpheus` user can't
    # write to /app, so put it under /tmp (or override via CELERY_BEAT_SCHEDULE_FILE).
    SCHEDULE_FILE="${CELERY_BEAT_SCHEDULE_FILE:-/tmp/celerybeat-schedule}"
    exec celery -A morph beat -l "${CELERY_LOG_LEVEL:-info}" \
        --schedule "$SCHEDULE_FILE"
    ;;
  shell)
    wait_for_db
    exec python manage.py shell
    ;;
  migrate)
    wait_for_db
    run_migrations
    ;;
  *)
    exec "$MODE" "$@"
    ;;
esac
