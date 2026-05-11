#!/usr/bin/env bash
# PostToolUse hook: run ruff format + check on the just-edited Python file.
# Exits 2 (visible to Claude) on lint failure so the model can re-edit.
# Silent on success.
set -u
path="$(jq -r '.tool_input.file_path // empty' 2>/dev/null)"
[[ -z "$path" ]] && exit 0
[[ "$path" != *.py ]] && exit 0
[[ "$path" == */migrations/* ]] && exit 0
[[ "$path" == *vendor/* ]] && exit 0
[[ ! -f "$path" ]] && exit 0

if ! command -v ruff >/dev/null 2>&1; then
  exit 0
fi

ruff format --quiet "$path" >/dev/null 2>&1 || true
if ! out="$(ruff check --quiet "$path" 2>&1)"; then
  echo "ruff check failed for $path:" >&2
  echo "$out" >&2
  exit 2
fi
exit 0
