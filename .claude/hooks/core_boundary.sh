#!/usr/bin/env bash
# PostToolUse hook: when a core/*.py file is edited, enforce that core/ does not
# import plugins.installed.* beyond the recorded baseline (wrong-direction
# coupling — see CLAUDE.md "Architectural compass"). Exits 2 (visible to Claude)
# so the model can re-edit. Silent on success.
set -u
path="$(jq -r '.tool_input.file_path // empty' 2>/dev/null)"
[[ -z "$path" ]] && exit 0
[[ "$path" != *.py ]] && exit 0
# Only relevant when the edit touches core/ (the guarded layer).
[[ "$path" != *"/core/"* && "$path" != core/* ]] && exit 0
[[ "$path" == *"/core/"*"/tests/"* ]] && exit 0

root="$(cd "$(dirname "$0")/../.." && pwd)"
[[ ! -f "$root/scripts/check_core_boundary.py" ]] && exit 0

if ! out="$(cd "$root" && python3 scripts/check_core_boundary.py 2>&1)"; then
  echo "core boundary check failed:" >&2
  echo "$out" >&2
  echo "core/ must reach plugins through hooks/contributions, not imports." >&2
  exit 2
fi
exit 0
