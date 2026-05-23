# Spec — Move `agent_core` plugin into Morpheus core

> User asks (in order):
> 1. "linda and agent integrations are part of morpheus, app is not needed"
> 2. "migrate code in morpheus or do what you think is best but remove that app"
> 3. **"agents shoud not be specialized, but one agent can work anything
>    and linda can activate serveral agents to do jobs in background and
>    report back to linda or anywhere else"** ← rewrites the agent layer
> 4. "agents can learn and linda can learn based on skills implementations
>    and during the talk with users"
>
> Visual hiding already shipped (e0b3fcb) — `agent_core` no longer
> appears in `/dashboard/apps/`, its dashboard pages fold under Linda.
> This doc covers the **physical** code migration AND the architectural
> collapse from 5 specialists → 1 generic Worker.

## Architectural pivot (2026-05-23)

**Old shape:** 5 specialized sub-agents (Concierge, Merchant Ops, Content
Writer, Pricing, Diagnostics) each with hard-coded scopes + prompts +
tool sets. Linda calls them one at a time via `delegate.invoke_agent`.

**New shape:** ONE generic `Worker` agent. Linda fans out N workers in
parallel via `delegate.spawn_workers(jobs=[…])`, each with its own
objective and optional skill-set narrowing. Results land in `AgentRun`
rows and (when post-run reflection produces something) `LindaMemory`
rows so the system *learns* across sessions.

| Surface | Old | New |
|---|---|---|
| Agent classes | 5 (concierge, merchant_ops, content_writer, pricing, diagnostics) | 1 (`worker`) |
| Tool selection | Per-class `scopes` whitelist | Caller scopes ∩ optional `skills=[]` filter |
| Linda → agents | `delegate.invoke_agent(name, objective)` (blocking, single) | `delegate.spawn_workers(jobs)` + `poll_workers(ids)` (parallel, async) |
| Learning | None — runs end and forget | Post-run reflection writes `LindaMemory`; Skills capture durable capability patterns |
| Specialization | Class definition | Skill bundle + prompt prelude (see `core.agents.skills`) |

Specialization becomes a **runtime composition** problem (pick the right
skill bundle), not a class-hierarchy problem. Adding a new "kind" of
worker is now a skill registration, not a `MorpheusAgent` subclass.

## Why this is split across phases

`plugins/installed/agent_core/` contains:

| Surface | Risk | Notes |
|---|---|---|
| Sub-agent class definitions (5 files) | LOW | Pure Python — just classes. Move freely. |
| Tool definitions (`@tool` decorators) | LOW | Pure Python. Move freely, update imports. |
| `services.py` (run_agent, scheduler hooks) | MEDIUM | Imports models. Move + update model imports. |
| `views.py` + `templates/` (Ops console, Runs, Background, Observability) | MEDIUM | Templates resolve by app dir; URL routes hardcode the plugin path. Move requires URL surgery. |
| **Models** (Agent, AgentRun, AgentApproval, AgentMemory, …) | **HIGH** | Tables exist on the live DB. Django ContentType app_label rows reference 'agent_core'. Any migration must preserve data exactly. |
| Migrations history (0001 → 0014) | HIGH | The Django migration graph hard-codes `agent_core` as the app_label. Pruning / squashing them would break re-runs. |

A clean "delete the plugin directory" requires phasing these in
order. Each phase is its own commit so a regression can be
bisected.

## Phase 1 — visual hide (DONE, commit e0b3fcb)

- `SYSTEM_PLUGINS` filter in apps_view drops agent_core from the catalog.
- Dashboard pages set to `nav='hidden'`.
- New "Linda" parent in base.html with the four sub-pages folded under it.
- SettingsPanel removed.

Merchant no longer sees `agent_core` anywhere in the UI.

## Phase 2 — Worker + spawn tools (low risk)

**Replaces** the old "move 5 specialist files" plan.

Create:

| Path | Purpose |
|---|---|
| `core/agents/builtin/__init__.py` | namespace |
| `core/agents/builtin/worker.py` | `Worker` class + system prompt |
| `core/assistant/tools/spawn.py` | `delegate.spawn_workers`, `poll_workers`, `wait_for_workers` |

The Worker is plain `core.agents` code — no plugin dependency. It is
registered via `agent_core/plugin.py:contribute_agents()` for now (so
the plugin still bootstraps it) and will move to a core registration
once the plugin disappears in Phase 4-5.

Linda's tool catalog in [core/assistant/tools/__init__.py](core/assistant/tools/__init__.py):

- **Keep**: `list_available_agents_tool` (now lists 1 worker).
- **Replace**: `invoke_agent_tool` → `spawn_workers_tool`, `poll_workers_tool`, `wait_for_workers_tool`.
- **Compatibility shim**: keep `delegate.invoke_agent(agent_name, objective)` as a thin alias that calls `spawn_workers` + `wait_for_workers`. Old tests + the Linda system prompt keep working.

Delete (or mark deprecated) the 5 specialist files in
`plugins/installed/agent_core/agents/` — their prompts can survive as
named entries in `prompt_registry` if anyone wants them as starter
skills, but the classes no longer instantiate.

Smoke test:

- `python -m py_compile <new files>`
- `python manage.py check`
- `python manage.py shell -c "from core.agents import agent_registry; print(agent_registry.all_agents())"` — should show `worker`.
- Hit Linda with "spawn 3 workers to draft taglines for 'Hamlet', 'Macbeth', 'Othello'" — expect 3 parallel `AgentRun` rows.

## Phase 3 — move services + views (medium risk)

Move:

| From | To |
|---|---|
| `plugins/installed/agent_core/services.py` | `core/agents/services.py` |
| `plugins/installed/agent_core/views.py` | `core/agents/views.py` |
| `plugins/installed/agent_core/templates/agent_core/*` | `core/agents/templates/agents/*` |
| `plugins/installed/agent_core/urls.py` | merge into `core/agents/urls.py` |

URL routing change:

- Old: `/dashboard/apps/agent_core/console/` (via plugin_page_router)
- New: `/dashboard/agents/console/` (direct URLconf mount)

The Linda sub-menu in `admin_dashboard/base.html` needs the new URLs.

301-redirect the old paths to the new ones so any bookmarks / external
links keep working:

```python
from django.views.generic import RedirectView

urlpatterns += [
    path('dashboard/apps/agent_core/console/', RedirectView.as_view(url='/dashboard/agents/console/', permanent=True)),
    # …same for runs, background, observability
]
```

## Phase 4 — model migration (HIGH risk, needs maintenance window)

This is the irreversible part. Models move from
`plugins.installed.agent_core` to `core.agents`.

**Option A (recommended) — keep table names via `Meta.db_table`:**

- Move model classes to `core/agents/models.py`.
- On each model, add `Meta.db_table = 'agent_core_<modelname>'` so the
  underlying tables don't rename.
- Generate `migrations.SeparateDatabaseAndState` operations: state-side
  moves the model to the new app, database-side does nothing (tables
  stay put).
- Run a data migration to update `django_content_type` rows:
  ```python
  ContentType.objects.filter(app_label='agent_core').update(app_label='core_agents')
  ```
- Generic ForeignKey relations need updating too — every
  `Metafield`/`AuditEvent`/etc. that targets agent_core models must
  flip its content_type FK to point at the new ContentType row. The
  data migration above plus the implicit FK update via Django's CT
  cache should handle this; verify in a staging environment first.

**Option B — rename tables:**

- Same as A but ALSO emit `migrations.AlterModelTable` to rename the
  tables (`agent_core_agent` → `core_agents_agent`, etc.).
- Cleanest final schema; highest risk during the migrate run.

**Pre-migration checklist:**

- [ ] Take a fresh DB backup.
- [ ] Schedule a 5-minute maintenance window.
- [ ] Test the migration against a copy of prod data in staging.
- [ ] Confirm `ContentType.objects.filter(app_label='agent_core').exists()` is False after.
- [ ] Spot-check that AgentRun rows still resolve via the new model.

**Post-migration:**

- [ ] Remove `plugins.installed.agent_core` from `MORPHEUS_DEFAULT_PLUGINS`.
- [ ] Delete `plugins/installed/agent_core/` directory.
- [ ] Delete the empty `agent_core_*` migration entries from `django_migrations` if Option B was used.

## Phase 5 — cleanup

- Update CLAUDE.md to reflect that agent code lives in `core/agents/`.
- Update any specs / docs that reference the old path.
- Search the codebase for stray `agent_core` mentions:
  ```bash
  rg 'agent_core' --type py --type html --type md
  ```

## Acceptance

- `grep -rn 'plugins.installed.agent_core' .` returns 0 hits (other
  than this spec).
- `python manage.py check` clean.
- `python manage.py migrate --check` clean.
- The merchant's experience is unchanged from Phase 1 — same Linda
  sub-menu, same URLs work (via redirects for legacy bookmarks).

## What's shipped right now (post-pivot)

- **Phase 1** (e0b3fcb) — visual hide complete.
- **Phase 2** (this commit) — `Worker` + `delegate.spawn_workers` /
  `poll_workers` / `wait_for_workers` shipped. The 5 specialists are
  no longer registered; `delegate.invoke_agent` is a back-compat shim.
  Linda's system prompt updated to teach the spawn surface.

Still pending: Phase 3 (move services + views into core), Phase 4
(model migration), Phase 5 (cleanup). Phase 4 wants a maintenance
window before it runs.
