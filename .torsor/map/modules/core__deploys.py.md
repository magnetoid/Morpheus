---
type: map
status: derived
tags:
- map
links: []
created: '2026-10-23T04:51:49'
updated: '2026-10-23T04:51:49'
rules: []
---

# core/deploys.py

Symbols in `core/deploys.py`.

- L50 `backup_root()` (function)
- L54 `predeploy_dir()` (function)
- L58 `current_commit()` (function) — The commit this image was built from, when the platform says (Coolify sets
- L68 `version_key(text: str)` (function) — ``vX.Y.Z`` as numbers, for comparing releases; None for anything else.
- L74 `is_older(version: str, than: str)` (function)
- L79 `deploy_label()` (function) — The version being deployed, with its short commit when known: the backup's name.
- L87 `migration_plan()` (function) — The migrations ``migrate`` would apply now, and whether no migration was ever
- L99 `read_handoff()` (function)
- L106 `write_handoff(data: dict)` (function)
- L110 `clear_handoff()` (function)
- L114 `record_deploy()` (function) — Write this boot's DeployEvent from the marker. safe_migrate calls it before
- L153 `record_failed_attempt(migrations: list[str])` (function) — Record a deploy whose pre-deploy backup failed, so that the older release
- L176 `failed_backup_name(version: str)` (function) — The pre-deploy backup taken before ``version`` first migrated; '' when it
- L192 `notify_rollback(event)` (function) — Email the operators that this store went back to an older release. Called
- L228 `describe_backup(path: Path)` (function) — A backup file as ``{name, size, taken_at, label}``, from its name and size;
- L242 `latest_predeploy_backup()` (function) — The newest backup in the pre-deploy folder, as ``describe_backup`` gives it;
- L252 `running_release()` (function) — What this store runs, for Settings → Version & updates and Linda's
