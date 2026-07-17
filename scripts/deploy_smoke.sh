#!/usr/bin/env bash
# Post-deploy smoke: wait for production to converge on the MORPHEUS_VERSION
# committed in this checkout, then assert basic health. Run by
# .github/workflows/deploy-smoke.yml on every push to main; also runnable
# locally after a manual deploy.
set -euo pipefail

BASE_URL="${SMOKE_BASE_URL:-https://dotbooks.store}"
DEADLINE_SECS="${SMOKE_DEADLINE_SECS:-1500}" # Coolify builds take ~5-10 min
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
echo "expecting production to reach version $expected"

start=$(date +%s)
last=""
while :; do
  body=$(curl -sS --max-time 15 "$BASE_URL/readyz" 2>/dev/null || echo '{}')
  live_version=$(printf '%s' "$body" | python3 -c "import json,sys
try: d=json.load(sys.stdin)
except Exception: d={}
print(d.get('version',''))" 2>/dev/null || echo '')
  live_status=$(printf '%s' "$body" | python3 -c "import json,sys
try: d=json.load(sys.stdin)
except Exception: d={}
print(d.get('status',''))" 2>/dev/null || echo '')
  last="version=$live_version status=$live_status"
  if [ "$live_version" = "$expected" ] && [ "$live_status" = "ok" ]; then
    home=$(curl -sS -o /dev/null -w '%{http_code}' --max-time 15 "$BASE_URL/" || echo 000)
    if [ "$home" = "200" ]; then
      echo "SMOKE OK — $last, homepage 200"
      exit 0
    fi
    last="$last homepage=$home"
  fi
  now=$(date +%s)
  if [ $((now - start)) -ge "$DEADLINE_SECS" ]; then
    echo "SMOKE FAILED — production never converged ($last after ${DEADLINE_SECS}s)." >&2
    echo "Check the Coolify deploy queue (a stale in_progress build wedges it) and" >&2
    echo "force-trigger if the webhook was missed — see docs/OPERATIONS_RUNBOOK.md." >&2
    exit 1
  fi
  echo "waiting… $last"
  sleep "$POLL_SECS"
done
