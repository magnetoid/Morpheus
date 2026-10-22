# Apps consolidation, Wave 2 merge 1 (wishlist ← save_for_later) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fold save_for_later into wishlist by removing the save_for_later app, which never worked, so that wishlist is the one owner of saved and shared lists. The removal ships in two releases so the migration gate and the automatic rollback keep working.

**Architecture:** Nothing moves into wishlist, because save_for_later is a stub:
- it is off on every store and holds 0 rows;
- no code reads or writes its three tables;
- wishlist already has lists, guest lists, share links, GDPR export/erasure and Janus tools;
- inventory already owns back-in-stock alerts.

The two releases:
- **Release A (v0.123.0)** deletes the app's code and its `MORPHEUS_DEFAULT_APPS` line. Its tables stay, so a store put back on v0.122.1 still finds them.
- **Release B (v0.123.1)** is pushed once A is live. A `plugins` app migration drops the tables, built with two new helpers in `core/migration_ops.py` that the rest of Wave 2 reuses: `leftover_table_drops()` and `forget_apps()`.

**Tech Stack:**
- Django 6.1 migrations;
- `core.migration_ops.DropLeftoverModel` (v0.122.1);
- the migration gate (`core/migration_safety.py`, v0.119.0);
- `manage.py release`;
- the CI ratchets (`scripts/check_plugin_standard.py`, `check_plugin_boundary.py`, `check_core_boundary.py`).

**Spec:** [`docs/plans/apps-consolidation-2026-10.md`](../../plans/apps-consolidation-2026-10.md), "Wave 2: merges": the row `wishlist | save_for_later | Same concept.` and the Order line, where wishlist comes first. The evidence is in [`docs/plans/apps-review-2026-10/merch.md`](../../plans/apps-review-2026-10/merch.md) §M5: "it is off everywhere and a stub, `SharedWishlist` duplicates `Wishlist.share_token`, and back-in-stock duplicates inventory."

## Global Constraints

- **Wave 2 rules (spec).** One merge per release; keep settings keys; move config rows in a data migration; keep old agent-tool names as aliases for one release; add a `MIGRATING.md` section; pass the disable suite. save_for_later has no settings keys, an empty config row and no agent tools, so only the last two apply.
- **A push to `main` deploys all four stores.** Each release runs `manage.py release` (version bump plus a dated `docs/RELEASE_NOTES.md` entry).
- **Release B is pushed only after Release A serves on all four stores.** Its contract says the previous release reads none of the tables, which is true only of A.
- **A migration that drops a table carries `morpheus_contract = "<why it is safe>"`.** Without one, `release` and `release --check` refuse it (`core/migration_safety.py`).
- **The pre-commit hook refuses the uppercase SQL statement that drops or truncates a table** in any added line, docs included. No document or comment spells it out.
- **`.claude/hooks/no_migration_writes.sh` refuses Edit/Write on migration files.** Write a hand-made migration through a script, then prove there is no drift with `makemigrations --check`.
- **Branch `feat/apps-wave-2-wishlist` in `/Users/magnetoid/coding/morph`; no worktree** (owner rule).
- **Live checks are read-only. Never `force_login` on a store.**
- **`git add` takes explicit paths only.** `git rm` stages deletions. A private note was once swept into a release commit by `git add -A … docs`.
- **Commits end with** `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`.
- **Tests:** `DATABASE_URL='sqlite:///:memory:' REDIS_URL='redis://127.0.0.1:6379/15' .venv/bin/python manage.py test <labels> --noinput`. The full suite also sets `MORPHEUS_EXTRA_APPS='plugins.installed.booking_marketplace,plugins.installed.dsers,plugins.installed.zendrop,plugins.installed.cjdropshipping,plugins.installed.aliexpress'`.
- **Docs ship in the same commit as the code they describe** (CLAUDE.md "Living document"). README figures are re-measured, never typed by hand.
- **No Janus tool is removed:** save_for_later registers none.
- **Rehearse Release B on Postgres before pushing it.** It drops tables and deletes rows, and SQLite hid the crash that v0.122.1's review found.

## Review Focus

1. **A store the guard puts back on v0.122.1 after A boots.** It still finds save_for_later's tables and its migration row, because A adds no migration. Pinned by Task 3, Step 4: the release gate lists no migration. Also pinned by Task 8: v0.122.1's code on the database A left.
2. **B on a database that never had save_for_later** (a new store, the test database, CI's Postgres job). The drops leave the absent tables alone and `forget_apps` deletes nothing. Pinned by the test database, which runs `plugins` 0003 at setup on SQLite and in CI's Postgres step, and by Task 8's fresh database.
3. **A save_for_later table with rows on someone else's deployment.** It is kept and logged, and loses its foreign keys, so its customer and product can still be deleted. Pinned by `core.tests.test_migration_ops` and by Task 8's seeded row.
4. **`forget_apps` removes only the named app's rows.** wishlist's migration history and switch stay. Pinned by Task 6's `ForgetAppsTests`.
5. **After A, every store's cart page renders and the Apps catalogue has no Save for later.** The `cart_summary_extra` slot keeps its other contributors (shipping, loyalty_points, eco_impact, dynamics). Pinned by the full suite and Task 5's live check.

---

## What goes, measured on 2026-10-23

dotbooks / supernatural / montenegro / irving, read-only (Appendix A):

| What | Value |
|---|---|
| `save_for_later_saveditem`, `save_for_later_pricesnapshot`, `save_for_later_sharedwishlist` | 0 / 0 / 0 / 0 rows each |
| save_for_later's switch (`PluginConfig`) | off on all four; the row holds no settings |
| its `django_migrations` rows | 1 on each store (`0001_initial`) |
| store environments naming it (`MORPHEUS_EXTRA_APPS`, `…_PLUGINS`, `MORPHEUS_DISABLED_APPS`, prod and preview) | none |
| wishlist, for comparison | 5 / 5 / 21 / 1 wishlists, 3 / 0 / 0 / 1 items, 0 shared |

What the app has:
- **Storefront:** one block, "Or save for later" in `cart_summary_extra`, whose buttons have nothing behind them. It never rendered on the four stores, where the switch is off. A fresh install with no switch row may treat the app as on.
- **Help and catalogue:** its guide, which says "none of that works yet", and its entry in the Apps catalogue.

It has no URLs, views, settings, beat jobs, hooks, Janus tools or GraphQL. Nothing outside the app imports it. Only documents name it:
- the README;
- historical plans;
- the generated `.torsor` map, which still lists Wave 1's apps (it is regenerated elsewhere and stays untouched);
- the stray `_test_settings_tmp.py` (an owner leftover, untouched).

## Decisions for the owner

1. **Nothing moves into wishlist.**
   - `SharedWishlist` duplicates `Wishlist.share_token`.
   - `SavedItem` duplicates `WishlistItem`.
   - `PriceSnapshot` belonged to price alerts that were never built.
   - Back-in-stock alerts are inventory's (`BackInStockSubscription`).
2. **No new feature is built.** A working "save for later" from the cart, or price-drop alerts, would be a new wishlist feature with its own plan.
3. **wishlist's guide stays as it is.** save_for_later's guide describes features that never existed, so there is nothing true to fold in.
4. **Two helpers join `core/migration_ops.py`** for the remaining merges, each of which removes at least one app. v0.122.1's `plugins` 0002 stays as released.
5. **Owner, 2026-10-23: wishlist's pages use wording that fits any shop, not the bookshop's.**
   - "No saved books yet", "Browse the shelf" and "A reading list, shared." go.
   - dot_books shows the same words as every other store; a theme can still override a page.
   - Every string is marked for translation, with a Serbian entry, because Montenegro serves `/sr/` and renders the shared page and the product-page button. Its main wishlist page is its own override and is untouched.

## Files

Release A:
- Delete: `plugins/installed/save_for_later/` (`__init__.py`, `app.py`, `apps.py`, `help.md`, `models.py`, `migrations/0001_initial.py`, `migrations/__init__.py`, `templates/save_for_later/blocks/move_buttons.html`, `tests/__init__.py`).
- Modify: `morph/settings.py`: the `MORPHEUS_DEFAULT_APPS` line and the `F19` comment line.
- Modify: `scripts/plugin_standard_baseline.json`, with `--save` (the entry `save_for_later:tests.missing` goes).
- Modify: `core/tests/test_removed_apps.py`: `REMOVED` and the docstring.
- Modify: `plugins/installed/wishlist/templates/wishlist/{wishlist,shared}.html`, `templates/wishlist/blocks/save_button.html`, and `locale/sr/LC_MESSAGES/django.{po,mo}`; test `plugins/installed/wishlist/tests/test_wording.py` (owner's wording rule).
- Modify: `README.md`, `docs/MIGRATING.md`, `docs/plans/apps-consolidation-2026-10.md`.
- The release tool modifies `docs/RELEASE_NOTES.md` and `MORPHEUS_VERSION`.

Release B:
- Modify: `core/migration_ops.py`: `leftover_table_drops()` and `forget_apps()`.
- Modify: `core/tests/test_migration_ops.py`: `LeftoverTableDropsTests` and `ForgetAppsTests`.
- Create: `plugins/migrations/0003_drop_save_for_later_tables.py`.
- Modify: `core/tests/test_removed_apps.py`: `SaveForLaterTablesTests`.
- Modify: `CLAUDE.md` (the two-release convention names the helpers), `docs/MIGRATING.md`, the consolidation plan's status, and the release files.

---

### Task 1: Branch and re-measure live

**Interfaces:** Produces the live numbers Task 2 relies on: every save_for_later table at 0 rows.

- [ ] **Step 1:** Confirm the branch: `git branch --show-current`. Expected: `feat/apps-wave-2-wishlist`, cut from `main` at d96a38e0 (v0.122.1).
- [ ] **Step 2:** Run Appendix A on the four stores. Expected: the "What goes" numbers, with `registered: True` (the app is installed, switched off). **If any save_for_later table holds a row, stop:** those rows belong to someone, and this plan changes.

### Task 2: Release A — save_for_later leaves the code, and wishlist speaks for any shop

**Files:**
- Delete: `plugins/installed/save_for_later/`.
- Modify: `morph/settings.py`, `scripts/plugin_standard_baseline.json`, and wishlist's three templates plus the Serbian catalogue (Steps 7–12).
- Test: `core/tests/test_removed_apps.py`, `plugins/installed/wishlist/tests/test_wording.py`.

**Interfaces:**
- Consumes: Task 1 (0 rows everywhere).
- Produces: `REMOVED` in `core/tests/test_removed_apps.py` includes `'save_for_later'`.

- [ ] **Step 1: Write the failing test.** In `core/tests/test_removed_apps.py`, replace the module docstring:

```python
"""Apps consolidation (docs/plans/apps-consolidation-2026-10.md): the apps that left the code
are gone. Wave 1's ten held no data and showed nothing; Wave 2 folded save_for_later into
wishlist. Their tables outlive them by one release."""
```

and end `REMOVED` with:

```python
    'lumina',
    # Wave 2: folded into wishlist (v0.123.0).
    'save_for_later',
)
```

- [ ] **Step 2: Run it.**

Run: `DATABASE_URL='sqlite:///:memory:' REDIS_URL='redis://127.0.0.1:6379/15' .venv/bin/python manage.py test core.tests.test_removed_apps --noinput`

Expected: FAIL, 2 failures:
- `test_the_removed_apps_are_not_installed`: `'plugins.installed.save_for_later' unexpectedly found`;
- `test_their_code_is_gone`: `['save_for_later'] != []`.

- [ ] **Step 3: Remove the app.**

```bash
git rm -r -q plugins/installed/save_for_later && rm -rf plugins/installed/save_for_later
python3 - <<'EOF'
from pathlib import Path
p = Path('morph/settings.py')
s = p.read_text()
for line in ("    #   F19  save_for_later         — save-for-later / wishlist upgrades\n",
             "    'plugins.installed.save_for_later',\n"):
    assert s.count(line) == 1, line
    s = s.replace(line, '')
p.write_text(s)
EOF
.venv/bin/python scripts/check_plugin_standard.py --save
```

Expected: the baseline loses `save_for_later:tests.missing` (32 → 31 entries).

- [ ] **Step 4: Run the tests and the gates.**

```bash
export DATABASE_URL='sqlite:///:memory:' REDIS_URL='redis://127.0.0.1:6379/15'
.venv/bin/python manage.py test core.tests.test_removed_apps core.tests.test_slot_parity core.tests.test_slot_render_live plugins.installed.wishlist plugins.installed.release_notes --noinput
.venv/bin/python manage.py check
.venv/bin/python manage.py makemigrations --check --dry-run
ruff check . && ruff format --check .
for s in check_core_boundary check_plugin_boundary check_plugin_standard; do .venv/bin/python scripts/$s.py | tail -1; done
```

Expected:
- the tests pass;
- `System check identified no issues`;
- `No changes detected`;
- ruff clean;
- the ratchets: `0` core imports, `112` plugin pairs, `31` known plugin-contract violations, no new ones.

- [ ] **Step 5: Search for what is left.**

```bash
grep -rn "save_for_later\|SaveForLater\|morpheus-sfl" --include='*.py' --include='*.html' --include='*.json' --include='*.yml' --include='*.js' --include='*.css' . | grep -v '^./.venv/\|^./docs/\|^./.torsor/\|^./_test_settings_tmp.py\|^./site/'
```

Expected: only `core/tests/test_removed_apps.py`. `README.md` is Task 3's.

- [ ] **Step 6: Commit.**

```bash
git add morph/settings.py scripts/plugin_standard_baseline.json core/tests/test_removed_apps.py
git commit -F - <<'EOF'
feat(apps): save_for_later leaves the code; wishlist is the one owner of saved and shared lists

save_for_later shipped switched off and never worked: its cart button had nothing behind
it and no code read or wrote its three tables, which hold no rows on any store. Wishlist
already keeps lists, guest lists and share links, and inventory owns back-in-stock
alerts, so nothing moves. Its tables stay a release, so a store put back on v0.122.1
still finds them.

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
EOF
```

- [ ] **Step 7: Write the failing tests for wishlist's wording** (owner, 2026-10-23). Create `plugins/installed/wishlist/tests/test_wording.py`:

```python
"""Wishlist's pages speak for any shop (owner, 2026-10-23), in every language a store serves.

They carried the bookshop's words ("No saved books yet", "Browse the shelf", "A reading
list, shared.") on every store but the one that overrides the wishlist page. The checks
use whole phrases: the test theme's own copy is full of the word "book".
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.template import engines
from django.templatetags.i18n import TranslateNode
from django.test import SimpleTestCase, TestCase
from django.utils.translation import trans_real
from djmoney.money import Money

from plugins.installed.catalog.models import Product
from plugins.installed.wishlist.services import add_item, get_or_create_wishlist, make_shareable

TEMPLATES = Path(__file__).resolve().parents[1] / 'templates' / 'wishlist'
BROWSER = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 Safari/605.1.15'


class WishlistWordingTests(TestCase):
    def test_an_empty_wishlist_speaks_for_any_shop(self):
        body = self.client.get('/wishlist/', HTTP_USER_AGENT=BROWSER, follow=True).content.decode()
        self.assertIn('Nothing saved yet.', body)
        self.assertIn('Browse the shop', body)
        self.assertNotIn('No saved books yet.', body)
        self.assertNotIn('Browse the shelf', body)

    def test_a_shared_wishlist_speaks_for_any_shop(self):
        user = get_user_model().objects.create_user(
            username='w@example.com', email='w@example.com', password='x'
        )
        product = Product.objects.create(
            name='Lamp', slug='lamp', sku='L1', status='active', price=Money(Decimal('10'), 'USD')
        )
        wishlist = get_or_create_wishlist(customer=user)
        add_item(wishlist=wishlist, product=product)
        url = f'/wishlist/shared/{make_shareable(wishlist)}/'
        body = self.client.get(url, HTTP_USER_AGENT=BROWSER, follow=True).content.decode()
        self.assertIn('Shared with you.', body)
        self.assertNotIn('A reading list, shared.', body)


class WishlistTranslationTests(SimpleTestCase):
    """Montenegro serves /sr/ and renders the shared page and the product-page button."""

    def test_every_string_is_marked_and_has_a_serbian_translation(self):
        catalog = trans_real.translation('sr')._catalog
        engine = engines['django'].engine
        msgids = [
            str(node.filter_expression.var.literal).replace('%', '%%')
            for path in sorted(TEMPLATES.rglob('*.html'))
            for node in engine.from_string(path.read_text()).nodelist.get_nodes_by_type(
                TranslateNode
            )
        ]
        self.assertGreaterEqual(len(msgids), 8)
        self.assertEqual([m for m in msgids if m not in catalog], [])
```

- [ ] **Step 8: Run it.**

Run: `DATABASE_URL='sqlite:///:memory:' REDIS_URL='redis://127.0.0.1:6379/15' .venv/bin/python manage.py test plugins.installed.wishlist.tests.test_wording --noinput`

Expected: FAIL, 3 failures:
- `'Nothing saved yet.' not found`;
- `'Shared with you.' not found`;
- `0 not greater than or equal to 8`.

- [ ] **Step 9: Change the three templates.**
  - **`wishlist/wishlist.html`**:
    - add `{% load i18n %}` under its `{% extends %}` line;
    - `Saved for later` → `{% trans "Saved for later" %}`;
    - `Your wishlist<span class="text-accent">.</span>` → `{% trans "Your wishlist" %}<span class="text-accent">.</span>`;
    - `Remove` → `{% trans "Remove" %}`;
    - `No saved books yet.` → `{% trans "Nothing saved yet." %}`;
    - `Browse the shelf` → `{% trans "Browse the shop" %}`.
  - **`wishlist/shared.html`**:
    - add `{% load i18n %}`;
    - `Shared wishlist` → `{% trans "Shared wishlist" %}`;
    - `A reading list, shared.` → `{% trans "Shared with you." %}`.
  - **`wishlist/blocks/save_button.html`**:
    - start with `{% load i18n %}`;
    - `♡ Save to wishlist` → `♡ {% trans "Save to wishlist" %}`.

  The CSS classes stay, because all four themes style them.
- [ ] **Step 10: Serbian entries.** Confirm the five new msgids are not in the catalogue yet: `grep -c '^msgid "\(Saved for later\|Nothing saved yet.\|Browse the shop\|Shared wishlist\|Shared with you.\)"$' locale/sr/LC_MESSAGES/django.po`. Expected: `0`. Then append to `locale/sr/LC_MESSAGES/django.po`:

```
# ── Wishlist (the wishlist app's own pages) ──
msgid "Saved for later"
msgstr "Sačuvano za kasnije"

msgid "Nothing saved yet."
msgstr "Još ništa nije sačuvano."

msgid "Browse the shop"
msgstr "Pregledajte ponudu"

msgid "Shared wishlist"
msgstr "Podijeljena lista želja"

msgid "Shared with you."
msgstr "Podijeljeno s vama."
```

Then compile it: `msgfmt --check-format -o locale/sr/LC_MESSAGES/django.mo locale/sr/LC_MESSAGES/django.po`. The committed `.mo` was compiled the same way: recompiling the unchanged `.po` gave identical bytes.

- [ ] **Step 11: Run the tests again, and compile the templates.**

```bash
export DATABASE_URL='sqlite:///:memory:' REDIS_URL='redis://127.0.0.1:6379/15'
.venv/bin/python manage.py test plugins.installed.wishlist plugins.installed.booking_marketplace.tests.test_serbian_catalog --noinput
.venv/bin/python manage.py shell -c "from django.template.loader import get_template; [get_template(n) for n in ('wishlist/wishlist.html', 'wishlist/shared.html', 'wishlist/blocks/save_button.html')]; print('compiled')"
```

Expected: `OK`, then `compiled`.

- [ ] **Step 12: Commit.**

```bash
git add plugins/installed/wishlist/templates/wishlist/wishlist.html plugins/installed/wishlist/templates/wishlist/shared.html plugins/installed/wishlist/templates/wishlist/blocks/save_button.html plugins/installed/wishlist/tests/test_wording.py locale/sr/LC_MESSAGES/django.po locale/sr/LC_MESSAGES/django.mo
git commit -m "fix(wishlist): its pages speak for any shop, and in Serbian on Serbian pages" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

### Task 3: Release A — docs, the full suite, the release

**Files:** `docs/MIGRATING.md`, `docs/plans/apps-consolidation-2026-10.md`, `README.md`; the release tool writes `docs/RELEASE_NOTES.md` and `morph/settings.py`.

**Interfaces:** Consumes Task 2's commit. Produces v0.123.0, staged and committed.

- [ ] **Step 1: MIGRATING.md.** Insert before `## v0.122.1 — the tables they left are dropped`:

```markdown
## v0.123.0 — save_for_later is gone

`save_for_later` is removed. It shipped switched off and never worked: its cart button had
nothing behind it, and no code read or wrote its three tables. Wishlist is the one owner of
saved and shared lists (`Wishlist.share_token`, `/wishlist/shared/<token>/`), and back-in-stock
alerts are inventory's. An out-of-tree app that lists `save_for_later` in `requires` must drop
it. Its tables stay in this release; v0.123.1 drops them the way v0.122.1 dropped Wave 1's.

---

```

- [ ] **Step 2: The consolidation plan's status.** In `docs/plans/apps-consolidation-2026-10.md`, insert after the line `## Wave 2: merges` and its blank line:

```markdown
**Status (v0.123.0, 2026-10-23):** wishlist ← save_for_later. save_for_later was a stub (off on
every store, nothing behind its cart button, 0 rows), so nothing moved: it left the code in
v0.123.0, and its tables go in v0.123.1.

```

- [ ] **Step 3: Run the full suite** (its count goes into the README):

```bash
DATABASE_URL='sqlite:///:memory:' REDIS_URL='redis://127.0.0.1:6379/15' MORPHEUS_EXTRA_APPS='plugins.installed.booking_marketplace,plugins.installed.dsers,plugins.installed.zendrop,plugins.installed.cjdropshipping,plugins.installed.aliexpress' .venv/bin/python manage.py test --noinput > .superpowers/sdd/2026-10-23-apps-wave-2-wishlist/full-a.log 2>&1; tail -3 .superpowers/sdd/2026-10-23-apps-wave-2-wishlist/full-a.log
```

Expected: `OK (skipped=11)`, about 5,255 tests. Clean the test run's media files afterwards (touch a marker before the run, then `find media -type f -newer <marker> -delete`).

- [ ] **Step 4: Cut the release.**

```bash
DATABASE_URL='sqlite:///:memory:' MORPHEUS_EXTRA_APPS='plugins.installed.booking_marketplace,plugins.installed.dsers,plugins.installed.zendrop,plugins.installed.cjdropshipping,plugins.installed.aliexpress' .venv/bin/python manage.py release --minor "Save for later is gone; Wishlist keeps saved and shared lists" \
  -m "The Save for later app is removed. It shipped switched off on every store and never worked: the button it added to the cart did nothing. Wishlist keeps saved and shared lists, and back-in-stock alerts are Inventory's." \
  -m "Wishlist's pages use words that fit any shop instead of the bookshop's (\"Nothing saved yet\", \"Browse the shop\"), and Serbian pages show them in Serbian."
```

Expected: `v0.122.1 -> v0.123.0`. The gate lists no migration.

- [ ] **Step 5: Re-measure the README** (Appendix B), after the cut, so the release is counted. Expected, against v0.122.1:
  - apps 103 → **102** (96 default + 6 opt-in);
  - storefront blocks 73 → **72** (19 slots);
  - templates 721 → **720**;
  - migrations **272**;
  - test functions **5,284** (save_for_later's one goes; the three wording tests arrive);
  - releases **305 in 125 days**.

  Events, tools, scopes, capabilities, GraphQL, routes, pages, panels, jobs and commands are unchanged. Edit `README.md`:
  - every `103` that counts apps becomes `102`: the tagline, the badge, the two `#-whats-in-the-box-all-103-apps` anchors, the contents line, the comparison row and the `## 🧩 What's in the box: all 103 apps` heading;
  - `**103** (97 on by default + 6 opt-in:` → `**102** (96 on by default + 6 opt-in:`;
  - `<summary><strong>CRM, retention & growth</strong> — 11 apps</summary>` → `— 10 apps`;
  - delete the row ``| `save_for_later` | Meant for save-for-later from the cart with price-drop and back-in-stock alerts; none of it works yet |``;
  - `Six say so in their own help: 3D and AR previews, the feed-style product rails, customer photo and video reviews, save-for-later, post-purchase sending, and the storefront stylist chat.` → `Five say so in their own help: 3D and AR previews, the feed-style product rails, customer photo and video reviews, post-purchase sending, and the storefront stylist chat.`;
  - `Measured at **v0.122.0 (22 October 2026)**` → `Measured at **v0.123.0 (23 October 2026)**`;
  - every other table figure becomes what Appendix B prints. The Tests row's run count is Step 3's `Ran N tests`, "on 2026-10-23".

  Then check that the anchors resolve: `grep -c "all-102-apps" README.md` (expected 3) and `grep -c "103" README.md`. Look at each remaining hit; none may count apps.
- [ ] **Step 6: Check and commit.**

```bash
DATABASE_URL='sqlite:///:memory:' MORPHEUS_EXTRA_APPS='plugins.installed.booking_marketplace,plugins.installed.dsers,plugins.installed.zendrop,plugins.installed.cjdropshipping,plugins.installed.aliexpress' .venv/bin/python manage.py release --check
git add docs/MIGRATING.md docs/plans/apps-consolidation-2026-10.md README.md docs/RELEASE_NOTES.md morph/settings.py
git commit -m "chore(release): v0.123.0 — Save for later is gone; Wishlist keeps saved and shared lists" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

Expected: `release --check` ends `✓ version v0.123.0 in sync with RELEASE_NOTES`.

### Task 4: Release A — a fresh review before it ships

**Interfaces:** Consumes Tasks 2–3 (range `d96a38e0..HEAD`). Produces the go to push.

- [ ] **Step 1:** Run `review-package` on `d96a38e0..HEAD`.
- [ ] **Step 2:** Dispatch a fresh reviewer, read-only, on the most capable model, with:
  - superpowers:requesting-code-review's `code-reviewer.md`;
  - the package;
  - this plan and the spec;
  - Review Focus 1 and 5;
  - the ledger's `Ruling:` lines.
- [ ] **Step 3:** Re-grade by effect. Fix Critical and Important findings RED→GREEN, then re-run the full suite. Ledger the minors. A fix changes docs or code, never the release commit's version.

### Task 5: Release A — push and check live

**Interfaces:** Consumes Task 4's go. Produces v0.123.0 on all four stores and the tag `v0.123.0`, which Release B's rollback guard needs.

- [ ] **Step 1: Before the push**, all four must hold:
  - githubstatus.com: Git Operations, Webhooks and Actions operational;
  - the Coolify deployments queue is empty;
  - `git fetch -q origin && git rev-parse --short origin/main` is `d96a38e0`;
  - tetra has at least 20 GB free (`df -h /`).
- [ ] **Step 2: Push.**

```bash
git checkout main && git pull --ff-only && git merge --ff-only feat/apps-wave-2-wishlist && git push origin main && git checkout feat/apps-wave-2-wishlist
SMOKE_DEADLINE_SECS=2400 bash scripts/deploy_smoke.sh
```

Expected:
- `SMOKE OK — every store serves v0.123.0`;
- `gh run list` shows `release` (the tag), `ci` and `deploy-smoke` green.

If GitHub starts no run within 5 minutes (its push events were lost on 2026-10-22):
1. queue each store through Coolify's API (POST `/api/v1/deploy?uuid=<app>&force=false`);
2. run the smoke yourself;
3. if a store stays down, run `scripts/deploy_guard.py rollback` by hand.

- [ ] **Step 3: Live check.** Run Appendix A. Expected on every store:
  - the three tables still there with 0 rows;
  - the migration row and the switch row still there;
  - `registered: False`;
  - a `v0.123.0` deploy row with 0 migrations and no backup (nothing to migrate);
  - 0 server errors in the last hour.

  Then `curl -s -o /dev/null -w "%{http_code}" "https://<store>/cart/?cb=$RANDOM"` on dotbooks.store, supernatural-shop.com and montenegro-experience.me. Expected: `200` each.

### Task 6: Release B — two helpers for leftover tables

**Files:** modify `core/migration_ops.py`; test `core/tests/test_migration_ops.py`.

**Interfaces:** Produces:
- `leftover_table_drops(tables: dict[str, str]) -> list[Operation]`, which maps a name in the migration's state to a table, children first;
- `forget_apps(*labels: str) -> Callable[[apps, schema_editor], None]`, for `migrations.RunPython`.

- [ ] **Step 1: Write the failing tests** in `core/tests/test_migration_ops.py`. Add these imports at the top: `from django.apps import apps as django_apps`, `from django.db.migrations.recorder import MigrationRecorder`, `from plugins.models import PluginConfig`. Extend the `core.migration_ops` import to `from core.migration_ops import DropLeftoverModel, forget_apps, leftover_table_drops`.

```python
# Two more methods for the existing DropLeftoverModelTests (they reuse its _create, which
# registers the cleanup):

    def test_leftover_table_drops_drop_a_table_that_is_there_and_empty(self):
        self._create()
        state = ProjectState()
        with connection.schema_editor() as editor:
            for operation in leftover_table_drops({'LeftoverProbe': TABLE}):
                after = state.clone()
                operation.state_forwards('plugins', after)
                operation.database_forwards('plugins', editor, state, after)
                state = after
        self.assertNotIn(TABLE, connection.introspection.table_names())

    def test_the_gate_sees_every_drop_leftover_table_drops_makes(self):
        migration = migrations.Migration('0099_probe', 'plugins')
        migration.operations = leftover_table_drops(
            {'LeftoverOne': 'probe_one', 'LeftoverTwo': 'probe_two'}
        )
        review = migration_safety.review(migration, ProjectState())
        self.assertTrue(review.blocks)
        self.assertEqual(len(review.findings), 2)


# And a new class at the end of the module:

class ForgetAppsTests(TransactionTestCase):
    """forget_apps: an app that left the code leaves no migration history or switch behind,
    and every other app keeps its own."""

    def test_only_the_named_apps_are_forgotten(self):
        recorder = MigrationRecorder(connection)
        recorder.record_applied('wave2_gone', '0001_initial')
        self.addCleanup(recorder.migration_qs.filter(app='wave2_gone').delete)
        PluginConfig.objects.create(plugin_name='wave2_gone', is_enabled=False)
        PluginConfig.objects.create(plugin_name='wave2_kept')
        wishlist_rows = recorder.migration_qs.filter(app='wishlist').count()

        with connection.schema_editor() as editor:
            forget_apps('wave2_gone')(django_apps, editor)

        self.assertFalse(recorder.migration_qs.filter(app='wave2_gone').exists())
        self.assertEqual(recorder.migration_qs.filter(app='wishlist').count(), wishlist_rows)
        names = PluginConfig.objects.filter(plugin_name__in=['wave2_gone', 'wave2_kept'])
        self.assertEqual(list(names.values_list('plugin_name', flat=True)), ['wave2_kept'])
```

- [ ] **Step 2: Run it.**

Run: `DATABASE_URL='sqlite:///:memory:' REDIS_URL='redis://127.0.0.1:6379/15' .venv/bin/python manage.py test core.tests.test_migration_ops --noinput`

Expected: ERROR, `ImportError: cannot import name 'forget_apps' from 'core.migration_ops'`.

- [ ] **Step 3: Write the helpers.** In `core/migration_ops.py`, change `from django.db import migrations` to `from django.db import migrations, models`, and append:

```python
def leftover_table_drops(tables: dict[str, str]) -> list:
    """The operations that drop a removed app's leftover tables, for a ``plugins`` app
    migration: each table enters this migration's state as an id-only model (its own app's
    state left with the app), then ``DropLeftoverModel`` drops it when it is there and
    empty. ``tables`` maps a name in this state to the table; name children first."""
    return [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.CreateModel(
                    name=name,
                    fields=[('id', models.BigAutoField(primary_key=True))],
                    options={'db_table': table},
                )
                for name, table in tables.items()
            ],
        ),
        *[DropLeftoverModel(name=name) for name in tables],
    ]


def forget_apps(*labels: str):
    """A ``RunPython`` function that deletes what ``django_migrations`` and ``PluginConfig``
    still hold for apps that left the code: an app given one of these names later starts
    from 0001, and no switch is left for an app that is gone."""

    def forget(apps, schema_editor):
        from django.db.migrations.recorder import MigrationRecorder  # noqa: PLC0415

        MigrationRecorder(schema_editor.connection).migration_qs.filter(app__in=labels).delete()
        apps.get_model('plugins', 'PluginConfig').objects.filter(plugin_name__in=labels).delete()

    return forget
```

- [ ] **Step 4: Run it again.** Same command. Expected: `OK (skipped=1)`; the skip is the Postgres-only test.
- [ ] **Step 5: Commit.**

```bash
git add core/migration_ops.py core/tests/test_migration_ops.py
git commit -m "feat(migrations): leftover_table_drops and forget_apps, for the apps Wave 2 removes" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

### Task 7: Release B — save_for_later's tables go

**Files:**
- Create: `plugins/migrations/0003_drop_save_for_later_tables.py`.
- Modify: `core/tests/test_removed_apps.py`, `CLAUDE.md`, `docs/MIGRATING.md`, `docs/plans/apps-consolidation-2026-10.md`.

**Interfaces:** Consumes Task 6's helpers and A live (Task 5). Produces the migration, under contract.

- [ ] **Step 1: Write the failing test.** Append to `core/tests/test_removed_apps.py`, and add `from django.db.migrations.recorder import MigrationRecorder` and `from plugins.models import PluginConfig` to its imports:

```python
SAVE_FOR_LATER_TABLES = {
    'SavedItem': 'save_for_later_saveditem',
    'PriceSnapshot': 'save_for_later_pricesnapshot',
    'SharedWishlist': 'save_for_later_sharedwishlist',
}


class SaveForLaterTablesTests(TransactionTestCase):
    """plugins 0003 on a store as v0.123.0 left it: save_for_later's three tables, its
    migration row and its switch."""

    def setUp(self):
        state = ProjectState()
        for name, table in SAVE_FOR_LATER_TABLES.items():
            fields = [('id', models.BigAutoField(primary_key=True))]
            state.add_model(ModelState('save_for_later', name, fields, {'db_table': table}))
        self.apps = state.apps
        with connection.schema_editor() as editor:
            for name in SAVE_FOR_LATER_TABLES:
                editor.create_model(self.apps.get_model('save_for_later', name))
        self.addCleanup(self._remove)
        recorder = MigrationRecorder(connection)
        recorder.record_applied('save_for_later', '0001_initial')
        self.addCleanup(recorder.migration_qs.filter(app='save_for_later').delete)
        PluginConfig.objects.create(plugin_name='save_for_later', is_enabled=False)

    def _remove(self):
        names = connection.introspection.table_names()
        with connection.schema_editor() as editor:
            for name, table in SAVE_FOR_LATER_TABLES.items():
                if table in names:
                    editor.delete_model(self.apps.get_model('save_for_later', name))

    def test_its_tables_migration_row_and_switch_go(self):
        drop = importlib.import_module('plugins.migrations.0003_drop_save_for_later_tables')
        state = MigrationLoader(connection).project_state(('plugins', '0002_drop_removed_app_tables'))
        with connection.schema_editor() as editor:
            for operation in drop.Migration.operations:
                after = state.clone()
                operation.state_forwards('plugins', after)
                operation.database_forwards('plugins', editor, state, after)
                state = after
        names = connection.introspection.table_names()
        self.assertEqual([t for t in SAVE_FOR_LATER_TABLES.values() if t in names], [])
        self.assertFalse(MigrationRecorder(connection).migration_qs.filter(app='save_for_later').exists())
        self.assertFalse(PluginConfig.objects.filter(plugin_name='save_for_later').exists())
```

- [ ] **Step 2: Run it.**

Run: `DATABASE_URL='sqlite:///:memory:' REDIS_URL='redis://127.0.0.1:6379/15' .venv/bin/python manage.py test core.tests.test_removed_apps --noinput`

Expected: ERROR, `ModuleNotFoundError: No module named 'plugins.migrations.0003_drop_save_for_later_tables'`.

- [ ] **Step 3: Write the migration through a script** (the hook refuses Edit/Write on migrations):

```bash
cat > plugins/migrations/0003_drop_save_for_later_tables.py <<'EOF'
"""save_for_later's tables (apps consolidation, Wave 2: wishlist ← save_for_later).

v0.123.0 took save_for_later out of the code and left its tables, so the release before
it still ran if a store was put back. Nothing has read them since. Each goes when it is
there and empty (core.migration_ops.DropLeftoverModel), and the app's django_migrations
row and switch go with them.
"""

from django.db import migrations

from core.migration_ops import forget_apps, leftover_table_drops


class Migration(migrations.Migration):
    dependencies = [('plugins', '0002_drop_removed_app_tables')]

    morpheus_contract = (
        'v0.123.0, the previous release, removed save_for_later and reads none of its tables.'
    )

    operations = [
        *leftover_table_drops(
            {
                'LeftoverSavedItem': 'save_for_later_saveditem',
                'LeftoverPriceSnapshot': 'save_for_later_pricesnapshot',
                'LeftoverSharedWishlist': 'save_for_later_sharedwishlist',
            }
        ),
        migrations.RunPython(forget_apps('save_for_later'), migrations.RunPython.noop),
    ]
EOF
ruff check plugins/migrations/0003_drop_save_for_later_tables.py && ruff format --check plugins/migrations/0003_drop_save_for_later_tables.py
```

- [ ] **Step 4: Run the tests and the drift check.**

```bash
export DATABASE_URL='sqlite:///:memory:' REDIS_URL='redis://127.0.0.1:6379/15'
.venv/bin/python manage.py test core.tests.test_removed_apps core.tests.test_migration_ops core.tests.test_migration_gate core.tests.test_migration_safety --noinput
MORPHEUS_EXTRA_APPS='plugins.installed.booking_marketplace,plugins.installed.dsers,plugins.installed.zendrop,plugins.installed.cjdropshipping,plugins.installed.aliexpress' .venv/bin/python manage.py makemigrations --check --dry-run
```

Expected: `OK (skipped=1)`, and `No changes detected`.

- [ ] **Step 5: Docs.**
  - **`CLAUDE.md`**, in "Convention — an app leaves in two releases (v0.122.0)". Replace
    ```
      - a removed app's tables, from a `plugins` app migration with
        `core.migration_ops.DropLeftoverModel`;
    ```
    with
    ```
      - a removed app's tables, from a `plugins` app migration built with
        `core.migration_ops.leftover_table_drops()` (a `DropLeftoverModel` per table) and
        `forget_apps()` (its `django_migrations` rows and switch);
    ```
  - **`docs/MIGRATING.md`**: insert before `## v0.123.0 — save_for_later is gone`:
    ```markdown
    ## v0.123.1 — save_for_later's tables are dropped

    `save_for_later_saveditem`, `save_for_later_pricesnapshot` and `save_for_later_sharedwishlist`
    are dropped when they are empty; one that still holds rows is kept, as in v0.122.1. The app's
    migration record and switch go too. From v0.123.1 you can go back to v0.123.0; to go further
    back, restore the pre-deploy backup first.

    ---

    ```
  - **The consolidation plan's status line**: replace `it left the code in\nv0.123.0, and its tables go in v0.123.1.` with `it left the code in\nv0.123.0 and its tables in v0.123.1. Next: reviews.`, and `(v0.123.0, 2026-10-23)` with `(v0.123.1, 2026-10-23)`.
- [ ] **Step 6: Commit.**

```bash
git add plugins/migrations/0003_drop_save_for_later_tables.py core/tests/test_removed_apps.py CLAUDE.md docs/MIGRATING.md docs/plans/apps-consolidation-2026-10.md
git commit -m "feat(apps): save_for_later's leftover tables are dropped" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

### Task 8: Release B — rehearse on Postgres

**Interfaces:** Consumes Task 7's commit and the tags `v0.122.1` and `v0.123.0`. Produces evidence for Review Focus 1–3.

- [ ] **Step 1:** Set up Appendix C: a scratch Postgres, the code trees `v0122_1`, `v0123` and `b` (HEAD), and the databases `fresh`, `path` and `skip`.
- [ ] **Step 2:** `fresh`: migrate on `b` from zero. Expected: exit 0, and none of the three tables.
- [ ] **Step 3:** `path`: migrate on `v0122_1`, then `v0123`. Run `migrate --check` and `check` on `v0122_1`'s code: this is the guard putting a store back after A. Then migrate on `b`. Expected:
  - the A step applies no migration;
  - v0.122.1's code is clean on the database A left;
  - `b` applies `plugins.0003_drop_save_for_later_tables` and the three tables are gone;
  - no `save_for_later` row in `django_migrations` or `plugins_pluginconfig`.
- [ ] **Step 4:** `skip`: migrate on `v0122_1`, seed one `SavedItem` (Appendix C `seed_sfl.py`), then migrate on `b`. Expected:
  - `save_for_later_saveditem` is kept with one WARNING;
  - no foreign key is left on it (`pg_constraint`);
  - deleting the seeded customer through `b`'s code works, and the row stays.
- [ ] **Step 5:** The guard's rollback after B: on `path`, run `v0123`'s `migrate --noinput`, `migrate --check`, `check` and `safe_migrate`. Expected: `No migrations to apply`, all clean.
- [ ] **Step 6:** Stop the server and delete the scratch directory. Record the matrix in the ledger.

### Task 9: Release B — the release, the final review, push and check live

**Interfaces:** Consumes Tasks 6–8. Produces v0.123.1 on all four stores.

- [ ] **Step 1:** Run the full suite, as in Task 3, Step 3. Expected: `OK`, with the new tests counted.
- [ ] **Step 2: Cut the release.**

```bash
DATABASE_URL='sqlite:///:memory:' MORPHEUS_EXTRA_APPS='plugins.installed.booking_marketplace,plugins.installed.dsers,plugins.installed.zendrop,plugins.installed.cjdropshipping,plugins.installed.aliexpress' .venv/bin/python manage.py release --patch "Save for later's empty tables are dropped" \
  -m "The three tables the Save for later app left behind are dropped when they are empty, with its migration record and its switch. One that still holds rows is kept, and the upgrade logs it."
```

Expected: `v0.123.0 -> v0.123.1` and `✓ migration contract — plugins.0003_drop_save_for_later_tables: v0.123.0, the previous release, removed save_for_later and reads none of its tables.`

- [ ] **Step 3:** Run `release --check`, then commit `docs/RELEASE_NOTES.md` and `morph/settings.py` as `chore(release): v0.123.1 — Save for later's empty tables are dropped`, with the trailer.
- [ ] **Step 4: The final whole-branch review** (executing-plans' Final Review): `review-package` on `d96a38e0..HEAD`, a fresh reviewer on the most capable model, Review Focus 1–5 and the ledger's rulings. Then the fix pass: each fix RED→GREEN, then the full suite.
- [ ] **Step 5: Push.** First, Task 5's pre-push checks, plus `git ls-remote --tags origin v0.123.0`: the guard puts a store back on that tag. Then push as in Task 5, Step 2. Expected: `SMOKE OK — every store serves v0.123.1`, and CI green, including the Postgres-only step.
- [ ] **Step 6: Live check.** Run Appendix A. Expected on every store:
  - the three tables absent;
  - 0 `save_for_later` migration rows;
  - no switch row;
  - a `v0.123.1` deploy row with 1 migration and a pre-deploy backup;
  - 0 server errors.
- [ ] **Step 7:** `git branch -d feat/apps-wave-2-wishlist`.

### Task 10: Record and close

- [ ] **Step 1:** Memory: a `releases-2026-10-23` note covering:
  - v0.123.0 and v0.123.1;
  - that save_for_later was a stub, so the merge was a removal;
  - the two helpers for the rest of Wave 2;
  - the next merge (reviews).

  Add its line in `MEMORY.md`.
- [ ] **Step 2:** Delete this plan's workspace once the final review is clean.

---

## Appendix A — `w2_live.py` and `w2_live.sh` (read-only)

`w2_live.py`, run with `manage.py shell <` in each web container:

```python
"""Apps Wave 2 (wishlist ← save_for_later), live and read-only."""
from datetime import timedelta
from pathlib import Path

from django.db import connection
from django.utils import timezone

from core.errors.models import ErrorEvent
from core.models import DeployEvent
from core.utils.site import store_name
from plugins.models import PluginConfig
from plugins.registry import app_registry

TABLES = ['save_for_later_saveditem', 'save_for_later_pricesnapshot', 'save_for_later_sharedwishlist',
          'wishlist_wishlist', 'wishlist_wishlistitem']
existing = set(connection.introspection.table_names())
counts = []
with connection.cursor() as cursor:
    for table in TABLES:
        if table not in existing:
            counts.append(f'{table}=absent')
            continue
        cursor.execute(f'SELECT count(*) FROM {connection.ops.quote_name(table)}')
        counts.append(f'{table}={cursor.fetchone()[0]}')
    cursor.execute("SELECT count(*) FROM django_migrations WHERE app = 'save_for_later'")
    recorded = cursor.fetchone()[0]
row = PluginConfig.objects.filter(plugin_name='save_for_later').first()
switch = 'no row' if row is None else ('on' if row.is_enabled else 'off')
print('W2LIVE', store_name(), '|', ' '.join(counts))
print('W2LIVE   switch:', switch, '| django_migrations rows:', recorded,
      '| registered:', app_registry.get('save_for_later') is not None)
print('W2LIVE   deploys:', ' ; '.join(
    f'{e.version} {e.commit[:7]} migrations={len(e.migrations)} backup={Path(e.backup).name or "-"}'
    for e in DeployEvent.objects.all()[:2]))
since = timezone.now() - timedelta(minutes=60)
print('W2LIVE   server errors in the last hour:', ErrorEvent.objects.filter(
    created_at__gte=since, kind=ErrorEvent.KIND_SERVER, level=ErrorEvent.LEVEL_ERROR).count())
```

`w2_live.sh`, run on tetra after `~/.ssh/tetra-ssh.sh "cat > /tmp/w2_live.py" < w2_live.py`, with `~/.ssh/tetra-ssh.sh "bash -s" < w2_live.sh`:

```bash
for uuid in ghtnqf6lw2bg5229lv1sf4h9 z10xg4j7yq8x1htipw12a368 fo8rvcg94bmcyi43e8iq9tvm j7xoogxjqgyakdsjw37eneuh; do
  web=$(docker ps --format '{{.Names}}' | grep "^web-$uuid" | head -1)
  docker cp /tmp/w2_live.py "$web:/tmp/w2_live.py"
  docker exec "$web" sh -c 'python manage.py shell < /tmp/w2_live.py' 2>&1 | grep '^W2LIVE'
  docker exec -u 0 "$web" rm -f /tmp/w2_live.py
done
rm -f /tmp/w2_live.py
```

## Appendix B — measuring the README

1. Run the measuring script from the Wave 1 session (`measure.py`, kept in the session scratchpad) with all opt-in apps loaded:

```bash
DATABASE_URL='sqlite:///:memory:' REDIS_URL='redis://127.0.0.1:6379/15' MORPHEUS_EXTRA_APPS='plugins.installed.booking_marketplace,plugins.installed.dsers,plugins.installed.zendrop,plugins.installed.cjdropshipping,plugins.installed.aliexpress' .venv/bin/python manage.py shell < measure.py 2>/dev/null | grep '^MEASURE'
```

   It prints one JSON line. Its fields map to the README table:

   | README row | JSON fields |
   |---|---|
   | apps | `apps_tree`, `apps_default`, `apps_optin` |
   | events | `events`, `subscriptions` |
   | tools | `tools`, `tools_approval` |
   | scopes, capabilities | `mcp_scopes`, `rbac_capabilities`, `gated_views` |
   | GraphQL | `gql_*` |
   | routes | `routes`, `routes_dashboard` |
   | pages, panels, blocks | `dashboard_pages`, `settings_panels`, `storefront_blocks`, `block_slots` |
   | jobs, commands | `beat_jobs`, `commands` |
   | releases | `releases`, `release_days` |
   | tests | `test_functions` |
   | Python | `py_lines`, `py_test_lines` |
   | templates | `templates` |
   | migrations | `migrations` |
   | ADRs | `adrs` |

2. `template_asset_lines` walks ignored build files too, so the README's template line count comes from tracked files:

```bash
git ls-files core plugins themes api morph morpheus scripts | grep -E '(/templates/.*\.html|\.css|\.js)$' | grep -v '\.min\.\|/vendor/' | tr '\n' '\0' | xargs -0 cat | wc -l
```

   That gave 72,976 at v0.122.1.

## Appendix C — the Postgres rehearsal

The recipe from v0.122.1. Run it from the session scratchpad; the owner rule is no worktrees.

```bash
S=<the session scratchpad>/pgr; mkdir -p $S/v0122_1 $S/v0123 $S/b
git archive v0.122.1 | tar -x -C $S/v0122_1
git archive v0.123.0 | tar -x -C $S/v0123
git archive HEAD | tar -x -C $S/b
initdb -D $S/data -U postgres --auth=trust -E UTF8 --locale=C
LC_ALL=C pg_ctl -D $S/data -o "-p 55432 -c listen_addresses=127.0.0.1 -c unix_socket_directories=''" -l $S/pg.log start
for d in fresh path skip; do createdb -h 127.0.0.1 -p 55432 -U postgres $d; done
```

The traps:
- without `LC_ALL=C`, it fails with "postmaster became multithreaded";
- the scratchpad path is too long for a Unix socket, hence `unix_socket_directories=''`;
- settings require SSL unless `DATABASE_SSL_MODE=disable`;
- an exported tree finds no `.env`, so the runner passes everything itself.

`run.sh <tree> <db> <log> <manage.py args…>`:

```bash
#!/bin/bash
S=<the session scratchpad>/pgr   # the same directory as above
tree=$1; db=$2; log=$3; shift 3
cd "$S/$tree" && env -i PATH=/usr/local/bin:/usr/bin:/bin HOME="$HOME" LC_ALL=C LANG=C DEBUG=True SECRET_KEY=rehearsal DATABASE_SSL_MODE=disable \
  DATABASE_URL="postgres://postgres@127.0.0.1:55432/$db" REDIS_URL=redis://127.0.0.1:6379/15 \
  /Users/magnetoid/coding/morph/.venv/bin/python manage.py "$@" > "$S/$log" 2>&1
echo "exit=$? $tree $db $*" >> "$S/$log"
```

`seed_sfl.py`, run on `v0122_1` with `run.sh v0122_1 skip seed.log shell -c "exec(open('$S/seed_sfl.py').read())"`:

```python
from decimal import Decimal

from django.apps import apps
from django.contrib.auth import get_user_model
from djmoney.money import Money

customer = get_user_model().objects.create_user(
    username='rehearsal@example.com', email='rehearsal@example.com', password='rehearsal-x1'
)
product = apps.get_model('catalog', 'Product').objects.create(
    name='Rehearsal', slug='rehearsal', sku='REH-1', status='active', price=Money(Decimal('10'), 'USD')
)
apps.get_model('save_for_later', 'SavedItem').objects.create(customer=customer, product=product)
print('SEEDED')
```

Delete the seeded customer on `b` with `get_user_model().objects.filter(email='rehearsal@example.com').delete()`. Expected: no IntegrityError, and `SELECT count(*) FROM save_for_later_saveditem` still `1`.

Check the foreign keys:

```bash
psql -h 127.0.0.1 -p 55432 -U postgres -d skip -Atc "select count(*) from pg_constraint where contype='f' and conrelid::regclass::text='save_for_later_saveditem'"
```

Expected: `0`.

Afterwards: `LC_ALL=C pg_ctl -D $S/data stop -m fast && rm -rf $S`.
