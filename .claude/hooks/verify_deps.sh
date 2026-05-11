#!/usr/bin/env bash
# PostToolUse hook: slopsquatting countermeasure.
# Triggered after any Edit/Write/MultiEdit. Acts only when the target is
# requirements.txt. For each NEW package (not present in HEAD's version),
# verifies (a) it exists on PyPI and (b) is already imported somewhere
# in the codebase. Blocks (exit 2) if either check fails.
set -u
path="$(jq -r '.tool_input.file_path // empty' 2>/dev/null)"
[[ -z "$path" ]] && exit 0
base="$(basename "$path")"
[[ "$base" != "requirements.txt" ]] && exit 0
[[ ! -f "$path" ]] && exit 0

# Diff HEAD vs working copy; pull added pkg names (lowercase, no version specifier)
added="$(git diff HEAD -- "$path" 2>/dev/null \
  | awk '/^\+[^+]/ { sub(/^\+/, ""); print }' \
  | sed -E 's/[[:space:]]*#.*$//; s/[[:space:]]+$//' \
  | grep -vE '^\s*$' \
  | sed -E 's/[<>=~!\[].*$//' \
  | tr '[:upper:]' '[:lower:]' \
  | sort -u)"

[[ -z "$added" ]] && exit 0

failures=""
while IFS= read -r pkg; do
  [[ -z "$pkg" ]] && continue
  # 1. PyPI presence check (HEAD without body).
  code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 "https://pypi.org/pypi/$pkg/json" 2>/dev/null)"
  if [[ "$code" != "200" ]]; then
    failures+="  - $pkg → not found on PyPI (HTTP $code) — possible hallucination\n"
    continue
  fi
  # 2. Usage check — is this package already imported anywhere? Allow
  # common stdlib-shaped dashes/underscores.
  importable="${pkg//-/_}"
  if ! grep -RqE --include='*.py' "^[[:space:]]*(import|from)[[:space:]]+(${pkg}|${importable})([[:space:]]|\.|$)" --exclude-dir='.venv' --exclude-dir='vendor' --exclude-dir='.git' . 2>/dev/null; then
    failures+="  - $pkg → on PyPI but not imported anywhere; justify in commit message or remove\n"
  fi
done <<< "$added"

if [[ -n "$failures" ]]; then
  printf 'verify_deps: new packages in requirements.txt need review:\n' >&2
  printf '%b' "$failures" >&2
  exit 2
fi
exit 0
