# Spec — Move `media` plugin into Morpheus core

> User ask (2026-05-23, item 3 of the 7-point dashboard cleanup):
> "Media app should be in morpheus core as main part of Morpheus OS"
>
> Same shape as the queued `docs/plans/agent-core-into-core.md` migration,
> but **smaller** — one model, six views, three templates. Validates the
> playbook before agent_core (next pass).

## Why media belongs in core

Every plugin that uploads or references a file uses `MediaAsset`. It's
the de-facto asset registry — moving it to core declares that intent.
Same logic that makes `core.audit`, `core.hooks`, `core.i18n` core.

## Surface inventory (what moves)

```
plugins/installed/media/
├── apps.py                  — AppConfig name='plugins.installed.media'
├── app.py                — Plugin manifest (label, ready(), DashboardPage)
├── models.py                — MediaAsset (1 model)
├── views.py                 — library / upload / delete / edit_meta / picker / api_upload
├── urls.py                  — 6 path() routes, mounted at /dashboard/media/
├── templates/media/         — library.html, edit_meta.html, picker.html
└── migrations/0001_initial.py
```

Target layout:

```
core/media/
├── apps.py                  — AppConfig name='core.media', label='media'
├── models.py                — MediaAsset (db_table preserved)
├── views.py                 — same six views
├── urls.py                  — same six routes
├── templates/media/         — same three templates
└── migrations/
    ├── 0001_initial.py      — copied verbatim from the plugin's 0001
    └── 0002_state_only.py   — SeparateDatabaseAndState noop (see Phase 3)
```

The plugin manifest (`app.py`) does NOT move. Instead, `morpheus`
core gets a small `register_media()` hook that mounts the URLs + the
sidebar entry. This is the same pattern other core modules use.

## External references (what changes elsewhere)

`grep -rn "plugins.installed.media" --include='*.py' .` finds:

| File | What | Action |
|---|---|---|
| `core/assistant/tools/ecommerce.py:697` | `from plugins.installed.media.models import MediaAsset` | Update to `from core.media.models import MediaAsset` |
| `core/management/commands/morph_backup.py:89` | Filesystem path only — not the model | No change needed |
| `morph/settings.py:81` | `'plugins.installed.media'` in MORPHEUS_DEFAULT_APPS | Remove |
| `morph/settings.py:335` | `MEDIA_ROOT = BASE_DIR / 'media'` | No change — that's the Django filesystem root, unrelated to the plugin |

INSTALLED_APPS picks up `core.media` via the existing `core.*` glob (or
explicit add — check current settings).

## Phase 1 — Code move (low risk, reversible)

1. Create `core/media/` with:
   - `__init__.py` (empty)
   - `apps.py`:
     ```python
     class MediaConfig(AppConfig):
         name = 'core.media'
         label = 'media'          # ← keep label = 'media' so app_label
                                   #   on every ContentType / migration row
                                   #   stays unchanged
     ```
   - `models.py` — copy from plugin, add:
     ```python
     class MediaAsset(models.Model):
         …existing fields…

         class Meta:
             app_label = 'media'              # explicit, in case Django
                                              # mis-guesses
             db_table = 'media_mediaasset'    # preserve table name
     ```
   - `views.py` — copy verbatim
   - `urls.py` — copy verbatim, update the dotted-path import
   - `templates/media/` — copy all three templates verbatim
   - `migrations/__init__.py` (empty)

2. Add `core.media` to `INSTALLED_APPS` in `morph/settings.py` (insert
   in the `core.*` block).

3. **Don't yet** remove `plugins.installed.media` from
   `MORPHEUS_DEFAULT_APPS` — both exist briefly so we can compare
   `Vendor` model resolution etc. before flipping.

4. Update the one real import (`core/assistant/tools/ecommerce.py:697`)
   to `from core.media.models import MediaAsset`.

5. Smoke locally: `python -m py_compile core/media/*.py`.

## Phase 2 — Mount URLs + sidebar from core (low risk)

Currently the plugin does:
```python
self.register_urls('plugins.installed.media.urls', prefix='dashboard/media/', namespace='media')
```

After Phase 1 we add the equivalent mount to `morph/urls.py`:
```python
path('dashboard/media/', include('core.media.urls', namespace='media')),
```

Sidebar entry: the existing hardcoded `<a href="/dashboard/media/">` in
`admin_dashboard/base.html:529` keeps working — the URL is unchanged.
Drop the `DashboardPage` from the plugin (it's `nav='hidden'` already).

## Phase 3 — Model migration (HIGH risk, needs maintenance window)

The DB still has a `media_mediaasset` table created by the plugin's
0001_initial. After Phase 1 there are TWO Django apps that think they
own this table — `plugins.installed.media` AND `core.media`. Django
will refuse to start because `MediaAsset` is declared in two app
labels (`media` and `media`). Need to:

1. **Disable the plugin first.** Set `name = ''` or remove from
   MORPHEUS_DEFAULT_APPS so its `apps.py` doesn't run, freeing
   the `media` app_label namespace for `core.media`.

2. **Generate a state-only migration** in `core.media/migrations/0002`:
   ```python
   from django.db import migrations
   class Migration(migrations.Migration):
       dependencies = [('media', '0001_initial')]
       operations = [
           migrations.SeparateDatabaseAndState(
               state_operations=[],   # nothing — model is identical
               database_operations=[], # nothing — table already exists
           ),
       ]
   ```
   This is a marker so Django's migration graph records that `core.media`
   knows about the table.

3. **Run on live**:
   ```bash
   docker exec <web-container> python manage.py migrate media --fake 0001_initial
   docker exec <web-container> python manage.py migrate media 0002
   ```
   The `--fake 0001_initial` tells Django: "this migration is already
   applied" (since the table really does exist from when it was a plugin).

4. **Update django_content_type rows** (no-op if app_label stayed
   as `'media'` because we kept `Meta.app_label = 'media'`):
   ```python
   from django.contrib.contenttypes.models import ContentType
   # Verify nothing references the old plugin app_label.
   ContentType.objects.filter(app_label='media').count()  # should be > 0
   ```

5. Verify: `MediaAsset.objects.count()` returns the same number as
   before the migration.

## Phase 4 — Delete the plugin directory

After Phase 3 succeeds on live:

1. `git rm -r plugins/installed/media/`
2. Remove from `MORPHEUS_DEFAULT_APPS` in settings.py
3. Smoke: redeploy, confirm `/dashboard/media/` still works
4. Smoke: hit `/dashboard/media/api/upload/` with a test image

## Acceptance

- `grep -rn 'plugins.installed.media' .` returns 0 hits (other than
  this spec).
- `python manage.py check` clean.
- `python manage.py migrate --check` clean.
- The merchant experience is unchanged — same URL, same UI, same model
  rows. The plugin directory is gone.

## Rollback plan

If Phase 3 goes wrong:

1. Re-add `plugins.installed.media` to `MORPHEUS_DEFAULT_APPS`.
2. Remove `core.media` from `INSTALLED_APPS`.
3. Revert the import in `core/assistant/tools/ecommerce.py`.
4. `docker compose restart web`.

The DB table stays in place either way — no destructive operation.

## Comparison with agent_core migration

| | media | agent_core |
|---|---|---|
| Models | 1 (MediaAsset) | 5+ (AgentRun, AgentStep, AgentConversation, AgentMessage, AgentApprovalRequest, BackgroundAgent…) |
| Views | 6 | ~12 (chat, runs, observability, background…) |
| Templates | 3 | ~8 |
| Hooks | none | Celery beat, multiple tasks |
| Risk | LOW | MEDIUM |
| Time | ~1 hour | ~3 hours |

**Doing media first validates** the SeparateDatabaseAndState +
Meta.db_table playbook on the smallest possible surface. If it works
clean, the same template applies to agent_core in the next session.

## What I'm doing right now

Writing this spec. **Not executing** — Phase 3 is a live-DB operation
that needs deliberate timing (not the end of a long session, not when
the merchant might be uploading). Queue it for a dedicated next pass.
