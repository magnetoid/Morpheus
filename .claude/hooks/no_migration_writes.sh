#!/usr/bin/env bash
# PreToolUse hook: block manual writes to Django migration files.
# Migrations come from `python manage.py makemigrations`; manual edits
# cause schema drift no test catches until a prod migrate fails.
set -u
path="$(jq -r '.tool_input.file_path // empty' 2>/dev/null)"
[[ -z "$path" ]] && exit 0

# __init__.py is hand-maintained; everything else under migrations/ is generated.
if [[ "$path" == *"/migrations/"* && "$(basename "$path")" != "__init__.py" ]]; then
  echo "no_migration_writes: refusing to write to $path." >&2
  echo "  Generate this via 'python manage.py makemigrations <app>' instead." >&2
  echo "  If a manual edit is truly required, run the hook bypass once." >&2
  exit 2
fi
exit 0
