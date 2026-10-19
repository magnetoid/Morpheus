# Safe deploys for our stores — design

Owner's ask (2026-10-18): "improve update and upgrade system". Owner's decisions
(2026-10-19): serve our own four stores first; when a new version fails, put the
code back automatically and restore data only by hand; guard the current Coolify
setup rather than move the stores to rolling updates; the five parts below as
proposed, the restore page and the rollback email included.

## Where we are (verified 2026-10-19)

- Every store is a Coolify **Docker Compose** application with health checks off
  (Coolify API: `build_pack: dockercompose`, `health_check_enabled: false`).
  Coolify's rolling update, which keeps the old container when the new one fails
  its check, needs a non-Compose app, so it never applies: a deploy replaces the
  containers, which is also the short 503 every deploy shows.
- The web container's entrypoint (`scripts/docker-entrypoint.sh`, `web` mode) waits
  for the database, runs `python manage.py migrate --noinput`, then starts
  gunicorn. Nothing backs up the database before a migration.
- Backups: `core/management/commands/morph_backup.py` (`pg_dump -Fc`, media as a
  tar, `--dest`, `--keep` default 7, `--no-media`), run nightly at 03:30 UTC by the
  backups app (`plugins/installed/backups/tasks.py`). There is no restore command.
- After every push, `deploy-smoke` (`.github/workflows/deploy-smoke.yml`,
  `scripts/deploy_smoke.sh`) polls each store's `/readyz` until it reports the
  pushed `MORPHEUS_VERSION`, and goes red when one doesn't by the deadline.
  Nothing acts on a red run.
- Settings → Version & updates (`plugins/installed/release_notes/views.py`) shows
  the release notes, an "Update now" button that needs a `.git` checkout and
  `MORPHEUS_SELF_UPDATE_ENABLED` (neither exists in our image), and per-app
  "Update" buttons that need a signed manifest nobody publishes. Linda's
  `updates.apply` tool calls the same dead path.
- Coolify's deploy endpoint takes no commit; an application carries a
  `git_commit_sha` (ours read `HEAD`).

## The design

### 1. A backup before any migration

Before `migrate`, the entrypoint runs `python manage.py predeploy`:

- It asks Django for unapplied migrations (`migrate --check` semantics). None: it
  does nothing, so most deploys stay as fast as today.
- Some: it runs `morph_backup --no-media --dest <backup dir>/pre-deploy --keep 5`
  (the database only; migrations never touch media), labelled with the version
  being deployed, in its own folder so deploys never rotate out the nightly
  copies.
- If that backup fails, it exits non-zero and the entrypoint stops before
  migrating. The store is then down, and part 3 puts the previous version back,
  on the schema it knows, because nothing was migrated.

After a successful start, the web process records the boot in a core table,
`DeployEvent` (version, commit when known, time, the pre-deploy backup's file, the
migrations applied). The page in part 5 and the rollback notice in part 3 read it.

### 2. Migrations the previous version can run on

Putting the old code back after a migration is safe only if the old code still
works on the new schema. A CI step, `scripts/check_migration_safety.py`, reads the
migrations a change adds and fails on any operation the previous release could
trip over: `RemoveField`, `DeleteModel`, `RenameField`, `RenameModel`, an
`AlterField` that makes a column `NOT NULL` without a default, and raw SQL. Such a
change ships in two releases: the first stops using the column, the second
removes it and says so on the migration (`morpheus_contract = "<why it is safe:
nothing reads it since vX.Y.Z>"`), which the check accepts.

### 3. The code goes back automatically

When `deploy-smoke` finds a store that never reports the new version healthy by
its deadline, it runs `scripts/deploy_guard.py rollback <store>`:

1. Finds the store's last good commit: the newest release tag older than the
   failed one.
2. Pins the store to it through the Coolify API (`git_commit_sha`) and deploys.
3. Waits for `/readyz` to report that version, then leaves the store pinned, so a
   repeat of the webhook cannot redeploy the broken commit.

On the next push to `main`, `deploy-smoke` first unpins every pinned store
(`git_commit_sha` back to `HEAD`) and deploys it, so a fix reaches every store.

The email comes from the store itself. On boot the web process compares its
version with the highest one in `DeployEvent`; lower means it was rolled back. It
records that once, shows it on the Version & updates page, and emails
`ERROR_ALERT_EMAILS` (else the superusers, else the store contact): which version
failed, which one runs now, and which pre-deploy backup holds the data from just
before the failed migration.

### 4. Restoring data, by hand

`manage.py morph_restore <file> --confirm "<store name>"` restores a backup:
maintenance mode on, other database sessions ended, `pg_restore --clean
--if-exists --no-owner`, maintenance mode off. A superuser-only page on
Settings → Version & updates lists the pre-deploy and nightly backups (time,
version, size) and runs the same restore in the background. Before it starts, it
says what the backup does not contain, from the database itself ("4 orders and 2
new customers since 14:02 will be lost"), and asks for the store's name typed
out.

### 5. A Version & updates page that tells the truth

The page shows the running version, its commit and deploy time, the latest
pre-deploy backup, and any rollback. Where the platform cannot update itself (no
`.git`, which is every Docker install), the "Update now" and per-app buttons give
way to one line: this store updates when a new version is released. Linda's
`updates.status` says the same, and `updates.apply` answers that it can't run
here instead of failing.

### Self-hosted installs

Parts 1, 2, 4 and 5 live in the app and work the same anywhere. Part 3 needs a
deploy platform's API; `docs/UPDATING.md` documents the guard script and the
contract it expects (deploy a commit, read `/readyz`), with Coolify as the
example.

## Order of delivery

Separate releases, each useful alone: (1) the pre-deploy backup and `DeployEvent`,
with the honest page (part 5); (2) the migration check in CI; (3) the restore
command and page; (4) the automatic rollback and its email.

## To verify before building on it

1. That pinning `git_commit_sha` on a Compose app and deploying builds that
   commit, and that a push webhook then redeploys the pin rather than `HEAD`.
2. Whether the running image knows its commit (Coolify's `SOURCE_COMMIT`); the
   page shows the version alone if not.
3. That `pg_restore` is in the image (`pg_dump` is) and can end other sessions.
4. That maintenance mode blocks the storefront and the dashboard while a restore
   runs, apart from the superuser running it.

## Out of scope

Moving the stores to rolling updates (no 503 during deploys); off-site backups;
publishing the per-app update channel.

## Testing

`predeploy` with and without pending migrations, and with a failing backup
(exits non-zero, migrates nothing); the migration checker on safe, unsafe and
marked migrations; rollback detection from `DeployEvent`; `morph_restore` against
SQLite and with `pg_restore` mocked; the restore page's confirmation and its "will
be lost" counts; the page without `.git`; the guard script's Coolify calls against
a fake server.
