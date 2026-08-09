# booking_marketplace — prod schema reconciliation plan (`/shop/` 500)

**Date:** 2026-08-09
**Status:** PLAN — do not build/ship until reviewed. (Today a naive `0002` already
503'd prod once; this is the careful redo.)
**Symptom:** `https://dotbooks.store/shop/` returns 500.

---

## 1. Root cause (confirmed against prod)

`/shop/` → `booking_marketplace.views.products_list`, which filters
`BookableService.objects.filter(..., listing_kind='product')`. Prod's
`booking_marketplace_bookableservice` table has **no `listing_kind` column** →
`ProgrammingError: column does not exist` → 500.

Why the column is missing — a **squashed-migration divergence**:

- Prod's `django_migrations` records the historical chain
  `0001_initial … 0007_…` as applied, and has the tables those created.
- A prior session **squashed** that chain into a single edited `0001_initial`
  in the codebase (6 models, all fields) and deleted `0002…0007` from disk.
- Django tracks migrations by **name**: prod already had `0001_initial` applied,
  so on the next deploy it **skipped** the edited `0001` — the *new* models and
  columns it introduced were **never created on prod**. Fresh installs (and
  local sqlite) run the edited `0001` and get everything, which is why tests and
  `makemigrations --check` pass while prod is missing schema.

(Today's first attempt generated a `0002` by diffing against the *pre-squash*
`0001`, so its `CreateModel(Enquiry)` collided with a table prod already had →
crash-loop → 503. Reverted in v0.34.2.)

## 2. The complete gap (prod schema vs current models)

Measured 2026-08-09 (prod columns vs `model._meta.local_fields`):

**Missing columns on existing tables**
| Table | Missing columns |
|---|---|
| `booking_marketplace_bookableservice` | `listing_kind`, `itinerary`, `languages`, `latitude`, `longitude`, `meeting_point`, `what_to_bring` |
| `booking_marketplace_booking` | `addons`, `tier_breakdown` |
| `booking_marketplace_enquiry` | `addons`, `tier_breakdown`, `time_slot` |

**Missing tables entirely**
| Table | Model | Cols |
|---|---|---|
| `booking_marketplace_pricingtier` | `PricingTier` | 9 |
| `booking_marketplace_addon` | `AddOn` | 11 |

A `listing_kind`-only fix would leave the other 11 columns + 2 tables missing —
`/shop/` might load but booking detail / pricing / add-on paths would 500. The
reconciliation must cover **all** of the above.

Prod data safety: the base tables exist with rows, but the missing tables have
**0 rows** (they don't exist) and the missing columns hold no data — so adding
them is purely additive, no backfill.

## 3. The fix — one idempotent, DB-agnostic reconciliation migration

`plugins/installed/booking_marketplace/migrations/0002_reconcile_prod_schema.py`

**Shape:** `SeparateDatabaseAndState`
- `state_operations = []` — the models are **already** in Django's state via the
  edited `0001` (name-applied on prod; created outright on fresh installs). We
  change only the physical DB, never the migration-state.
- `database_operations = [RunPython(reconcile, noop)]`

**Why `RunPython` (introspection) and NOT `RunSQL … IF NOT EXISTS`:** the
migration must run on both Postgres (prod) and **sqlite** (tests/local). Postgres
supports `ADD COLUMN IF NOT EXISTS`, but **sqlite does not** — a `RunSQL` with
that clause is a syntax error under the test DB. Introspection + `schema_editor`
is idempotent on every backend and reuses Django's own DDL generation (no
hand-written `CREATE TABLE`).

```python
from django.db import migrations

_MODELS = ('PricingTier', 'AddOn')  # missing tables
_COLUMN_MODELS = ('BookableService', 'Booking', 'Enquiry')  # tables missing columns

def reconcile(apps, schema_editor):
    conn = schema_editor.connection
    existing_tables = set(conn.introspection.table_names())
    # 1) create wholly-missing tables (historical models carry all fields/FKs/indexes)
    for name in _MODELS:
        model = apps.get_model('booking_marketplace', name)
        if model._meta.db_table not in existing_tables:
            schema_editor.create_model(model)
    # 2) add missing columns on existing tables
    with conn.cursor() as cur:
        for name in _COLUMN_MODELS:
            model = apps.get_model('booking_marketplace', name)
            table = model._meta.db_table
            if table not in existing_tables:
                schema_editor.create_model(model)  # (defensive; shouldn't happen)
                continue
            present = {c.name for c in conn.introspection.get_table_description(cur, table)}
            for field in model._meta.local_fields:
                if field.column not in present:
                    schema_editor.add_field(model, field)

class Migration(migrations.Migration):
    dependencies = [('booking_marketplace', '0001_initial')]
    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[],
            database_operations=[migrations.RunPython(reconcile, migrations.RunPython.noop)],
        ),
    ]
```

**Behavior:**
- Fresh install / sqlite tests: `0001` creates everything, `reconcile` finds all
  tables+columns present → no-op. `makemigrations --check` → *No changes* (state
  unchanged from `0001`).
- Prod: `0001_initial` already applied by name (skipped); `0002_reconcile_prod_schema`
  is unapplied → runs → creates `addon`/`pricingtier` + adds the 12 columns →
  records applied. The phantom `0002_enable_by_default…0007` rows (no on-disk
  file) are ignored and don't collide (different name).

## 4. Verification matrix (all before ship)

1. **sqlite** — `DATABASE_URL='sqlite:///:memory:' python manage.py migrate` +
   full `booking_marketplace` suite green; `makemigrations --check` clean.
2. **Fresh Postgres** (docker) — `migrate` clean end-to-end.
3. **Simulated prod** (the critical test) — on a scratch Postgres: create the
   booking_marketplace tables **as prod has them** (drop the 12 columns + the 2
   tables), insert a `0001_initial` row into `django_migrations` **without**
   running it (fake-applied), then `migrate booking_marketplace` → assert `0002`
   creates exactly the missing objects with **no error**, and a second `migrate`
   is a clean no-op (idempotency).
4. **Post-deploy** — prod `migrate` applies `0002`; `/shop/` returns **200**;
   a booking PDP + a pricing/add-on path return 200; `/readyz` converges.

## 5. Risks & mitigations

- **sqlite vs Postgres DDL** → solved by introspection (§3), not `IF NOT EXISTS`.
- **FK/index creation** → `create_model` emits the model's FKs + declared
  indexes/constraints; the missing columns are plain (JSON/char/decimal/float),
  no cross-type FK retarget (the class of change that 503'd PR #62).
- **Re-runnability** → every step guards on existence; safe if partially applied.
- **Migration name** must not be one of the phantom prod names
  (`0002_enable_by_default`, `0003_…`, …) — use `0002_reconcile_prod_schema`.
- **No CI Postgres** (GitHub Actions billing-blocked) → run the simulated-prod
  test locally against a real Postgres before shipping; do not trust green sqlite
  for this migration.

## 6. Follow-up (separate, optional)

The codebase↔prod migration-history divergence (prod carries `0001…0007`, the
tree has one squashed `0001`) is now benign once `0002_reconcile` lands. A future
`--squashed`/clean-history cleanup is optional and out of scope here.
