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

# core/restore.py

Symbols in `core/restore.py`.

- L67 `RestoreError` (class) — A restore refused or failed, in words for the person who asked for it.
- L71 `RestoreBusy` (class) — Another restore is running.
- L75 `state_dir()` (function)
- L79 `running_path()` (function)
- L83 `_age(path: Path)` (function)
- L90 `_read(path: Path)` (function)
- L98 `is_running()` (function) — A restore is under way: its file exists and was touched lately.
- L104 `stalled()` (function) — A restore that stopped without reporting back: its file is there, but
- L113 `last()` (function) — How the latest restore ended, as ``run`` recorded it; None before the first.
- L118 `start(info: dict)` (function) — Close the store for a restore, or raise RestoreBusy while another runs.
- L133 `_write_last(outcome: dict)` (function)
- L141 `finish(outcome: dict)` (function) — Record how the restore ended, then open the store.
- L148 `heartbeat(path: Path, every: float=HEARTBEAT)` (function) — Touch ``path`` every ``every`` seconds while the block runs.
- L179 `RestoreGateMiddleware` (class) — Every page answers 503 "restoring" while a restore runs, before anything
- L184 `__init__(self, get_response)` (method)
- L187 `__call__(self, request)` (method)
- L198 `_now()` (function)
- L202 `kind_of(archive: Path)` (function) — Which list ``archive`` belongs to; '' for a file anywhere else.
- L212 `extract_dump(archive: Path, into: Path)` (function) — The backup's database dump, extracted into ``into``.
- L227 `end_other_sessions()` (function) — End every other session on this database, so the restore gets its locks.
- L241 `restore_database(dump: Path)` (function)
- L254 `_pg_connection(db: dict)` (function)
- L267 `_tail(text: str)` (function)
- L271 `_pg_restore(db: dict, dump: Path)` (function) — Replace the whole public schema with the backup's, in one transaction.
- L312 `_sqlite_restore(db: dict, dump: Path)` (function)
- L325 `clear_cache()` (function) — Drop every cached value: each describes the data the restore replaced. Only
- L337 `pre_restore_dir()` (function)
- L341 `back_up_current(stdout=None)` (function) — Back the current database up into pre-restore/; the new file's name.
- L356 `prune_pre_restore(restored: Path)` (function) — After a restore that worked: keep the newest PRE_RESTORE_KEEP copies, and
- L366 `run(archive: Path, *, confirm: str, by: str='', stdout=None)` (function) — Restore ``archive`` over the store's database; the outcome, as last.json
- L409 `_check(archive: Path, confirm: str, into: Path)` (function) — The backup's dump, once the restore may start; RestoreError naming what stops it.
- L421 `_restore(archive: Path, dump: Path, stdout)` (function)
- L447 `reload_web(pid: int)` (function) — Ask the gunicorn master for fresh workers. Each process keeps app
- L456 `losses(since: datetime)` (function) — What restoring a backup made at ``since`` replaces, as each app counts it
- L466 `backups()` (function) — The backups the restore screen offers, newest first: nightly, made before
- L482 `find(kind: str, name: str)` (function) — The listed backup a screen names by kind and file name, never by path.
- L490 `spawn(archive: Path, *, confirm: str, by: str, reload_pid: int=0)` (function) — Start ``manage.py morph_restore`` detached from the request, so it outlives
- L524 `backup_migrations(archive: Path)` (function) — The migrations a backup's database records, as ``(app, name)``; None when
- L535 `_dump_migrations(dump: Path)` (function)
- L557 `_copy_rows(sql: str)` (function) — The ``(app, name)`` rows of the django_migrations COPY block in pg_restore's SQL.
- L573 `missing_for(applied: set[tuple[str, str]])` (function) — The migrations this code has that a database recording ``applied`` lacks,
