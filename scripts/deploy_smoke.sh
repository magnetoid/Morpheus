#!/usr/bin/env bash
# Post-deploy smoke: wait for EVERY production store to converge on the
# MORPHEUS_VERSION committed in this checkout, then assert basic health. Run by
# .github/workflows/deploy-smoke.yml on every push to main; also runnable
# locally after a manual deploy.
#
# One push deploys every store (Coolify watches the repo once per app), so one
# store whose build failed must turn the commit red — until v0.87.2 only
# dotbooks.store was checked, and supernatural's failed build on 2026-10-08
# went unnoticed.
set -euo pipefail

# Space-separated. SMOKE_BASE_URL (singular) still works for a one-store check.
DEFAULT_URLS="https://dotbooks.store https://supernatural-shop.com https://montenegro-experience.me https://beta.irvingsurvival.com"
BASE_URLS="${SMOKE_BASE_URLS:-${SMOKE_BASE_URL:-$DEFAULT_URLS}}"
DEADLINE_SECS="${SMOKE_DEADLINE_SECS:-1500}" # Coolify builds take ~5-10 min, four of them in a queue
POLL_SECS=20

expected=$(python3 -c "
import re
src = open('morph/settings.py').read()
m = re.search(r\"MORPHEUS_VERSION = config\('MORPHEUS_VERSION', default='([^']+)'\", src)
print(m.group(1) if m else '')
")
if [ -z "$expected" ]; then
  echo "could not parse MORPHEUS_VERSION from morph/settings.py" >&2
  exit 1
fi
echo "expecting production to reach version $expected on: $BASE_URLS"

read_json_field() { # stdin: body; $1: field
  python3 -c "import json,sys
try: d=json.load(sys.stdin)
except Exception: d={}
print(d.get('$1',''))" 2>/dev/null || echo ''
}

# A store passes once /readyz reports the expected version with status ok and
# the homepage answers 200. Passed stores are not polled again. (A plain
# string, not an associative array: macOS ships bash 3.2 and this script is
# also run by hand after a manual deploy.)
done_hosts=" "
start=$(date +%s)
while :; do
  pending=""
  for base in $BASE_URLS; do
    case "$done_hosts" in *" $base "*) continue ;; esac
    body=$(curl -sS --max-time 15 "$base/readyz" 2>/dev/null || echo '{}')
    live_version=$(printf '%s' "$body" | read_json_field version)
    live_status=$(printf '%s' "$body" | read_json_field status)
    if [ "$live_version" = "$expected" ] && [ "$live_status" = "ok" ]; then
      home=$(curl -sS -o /dev/null -w '%{http_code}' --max-time 15 "$base/" || echo 000)
      if [ "$home" = "200" ]; then
        echo "OK  $base — version=$live_version status=ok homepage=200"
        done_hosts="$done_hosts$base "
        continue
      fi
      pending="$pending $base(version=$live_version homepage=$home)"
    else
      pending="$pending $base(version=${live_version:-?} status=${live_status:-?})"
    fi
  done
  if [ -z "$pending" ]; then
    echo "SMOKE OK — every store serves $expected"
    exit 0
  fi
  now=$(date +%s)
  if [ $((now - start)) -ge "$DEADLINE_SECS" ]; then
    echo "SMOKE FAILED — not every store converged after ${DEADLINE_SECS}s:$pending" >&2
    echo "Check the Coolify deploy queue (a stale in_progress build wedges it) and" >&2
    echo "force-trigger if the webhook was missed — see docs/OPERATIONS_RUNBOOK.md." >&2
    exit 1
  fi
  echo "waiting…$pending"
  sleep "$POLL_SECS"
done
