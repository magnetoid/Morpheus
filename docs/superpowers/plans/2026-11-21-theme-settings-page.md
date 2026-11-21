# Theme settings page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Merchants and Linda can read and change the active theme's settings. The merchant does it from a
dashboard card under Settings → Storefront, and a saved value reaches every worker within 10 s.

**Architecture:**
- **Themes.** They gain `set_config()` and a 10-second re-read, mirroring `Plugin.config_fresh_s`.
- **Shared helpers.** The form-field builder, the posted-form save loop and the setting describer move
  into `plugins/config_schema.py`, where an app panel, a theme page and Linda's tools all use them.
- **Storefront.** It contributes the page as a `DashboardPage(nav='settings', section='storefront')`.
- **Linda.** `theme.describe` and `theme.set` sit beside `theme.activate` in
  `core/assistant/tools/admin_ops.py`.

**Tech Stack:** Python 3.12, Django (version from `requirements.lock.txt`), the dashboard's settings form
template.

**Spec:** `docs/superpowers/specs/2026-11-21-theme-settings-and-christmas-design.md` (release 1 only;
release 2, the Christmas look, gets its own plan).

## Global Constraints

- **No migration.** `ThemeConfig` is unchanged, so `makemigrations --check --dry-run` stays clean.
- **Import boundaries.**
  - `core/` imports nothing from `plugins.installed.*`.
  - `storefront` imports nothing from `admin_dashboard` (the plugin-boundary ratchet). Shared code goes in
    `plugins/config_schema.py`.
  - Templates are not imports: storefront may render `admin_dashboard/plugin_settings.html`.
- **Gating.**
  - The page is `@staff_member_required` + `@require_capability('system.write')`, like every settings page.
  - `theme.describe` has scopes `['system.read']`.
  - `theme.set` has scopes `['system.write']` and `requires_approval=True`.
- **Which theme.** Only the **active** theme (`themes.registry.theme_registry.active`) is shown or
  changed.
- **Defaults leave every store as it is.** The release adds no theme setting.
- **Copy (verbatim).**
  - Card label: `Theme`.
  - Card hint: `Settings your active theme offers`.
  - Page heading: `Theme: <theme.label>`.
  - Empty schema: `The active theme, <theme.label>, has no settings.`
  - No active theme: a 404 with `No active theme.`
- **Running tests.**
  - Prefix every run with `DEBUG=True DATABASE_URL='sqlite:///:memory:' SECRET_KEY=test-key
    REDIS_URL=redis://127.0.0.1:6379/15`.
  - Use `.venv/bin/python`.
  - Lint with ruff 0.15.8 (`.venv/bin/ruff`).
- **Release.** Run `python manage.py release --minor …` to produce v0.185.0. Never hand-edit the version
  or the notes.

## Rulings (deviations from the spec's wording)

- **URL.** The page lives at `/dashboard/apps/storefront/theme/`, not `/dashboard/settings/theme/`.
  - Why: `settings/<str:category>/` is admin_dashboard's converter route. A literal beside it would be a
    shell edit for an app's page, and CLAUDE.md warns that such routes silently win or lose.
  - The card sits on Settings → Storefront as specified.
  - Cost if wrong: one `url=` on the `DashboardPage`.
- **Card label.** The card reads `Theme`, and the page heading names the theme.
  - Why: contributions are built once at wire time, so a label naming the theme would go stale after
    `theme.activate`.
- Task 5 amends both lines in the spec.

## Review Focus

1. **A theme activated by `MORPHEUS_ACTIVE_THEME`** (Dawnchild's case) has no `ThemeConfig` row. The
   first save must create the row with `is_active=False` and must not change which theme is active.
   Pinned in Task 1.
2. **A save made on one worker** must show on every other worker within 10 s, not only after a restart.
   Pinned in Task 1.
3. **One post holding an unticked switch and a number that isn't a number.** The switch turns off and the
   number keeps its stored value. Pinned in Task 2.
4. **Linda passing an unknown key, a wrong type, or a key marked `x-agent-writable: false`.** Each is
   refused, the message ends in `Nothing was changed.`, and nothing is stored. Pinned in Task 4.
5. **Staff without `system.write` while rbac enforces.** They are refused; anonymous users are sent to
   sign in; a superuser gets the page. Pinned in Task 3.

---

### Task 1: Theme config can be saved and stays fresh across workers

**Files:**
- Modify: `themes/base.py` (class attributes near line 116; `get_config` near line 163; add `set_config`)
- Test: `themes/test_theme_config.py` (create)

**Interfaces:**
- Produces:
  - `MorpheusTheme.config_fresh_s: float | None = 10.0`
  - `MorpheusTheme._config_read_at: float = 0.0`
  - `MorpheusTheme.set_config(self, key: str, value: Any) -> None`
  - `get_config()`, `get_config_value()` and `invalidate_config_cache()` keep their signatures.

- [ ] **Step 1: Write the failing tests** in `themes/test_theme_config.py` (`TestCase`).
  - Use the active theme (`theme_registry.active`, dot_books under tests).
  - Call `addCleanup(theme.invalidate_config_cache)` in `setUp`.
  - Tests:
    - `test_set_config_stores_the_value_and_this_process_reads_it_at_once`:
      `theme.set_config('tagline', 'A new line')`, then
      `assertEqual(theme.get_config_value('tagline'), 'A new line')` and
      `assertEqual(ThemeConfig.objects.get(theme_name=theme.name).config['tagline'], 'A new line')`.
    - `test_the_first_save_creates_the_row_without_activating_the_theme`:
      - Precondition: `ThemeConfig.objects.filter(theme_name=theme.name).exists()` is False.
      - After `set_config`, the row exists with `is_active is False`, and `theme_registry.active.name` is
        unchanged.
    - `test_another_worker_sees_a_save_within_ten_seconds`:
      - Build a second instance with `other = type(theme)()` and read `other.get_config()` once.
      - Save through `theme.set_config('tagline', 'Fresh')`.
      - Patch `themes.base.time.monotonic`:
        - at +9.0 s, `other.get_config_value('tagline') != 'Fresh'`;
        - at +10.0 s, it equals `'Fresh'`.
    - `test_themes_re_read_their_settings_every_ten_seconds`:
      `assertEqual(MorpheusTheme.config_fresh_s, 10.0)`.

- [ ] **Step 2: Run them and see them fail**
  Run: `<env> .venv/bin/python manage.py test themes.test_theme_config -v 2`
  Expected: FAIL (`AttributeError: … has no attribute 'set_config'`).

- [ ] **Step 3: Implement it in `themes/base.py`.**
  - `get_config` mirrors `plugins/base.py:301-329`:
    - drop the cache once `time.monotonic() - _config_read_at >= config_fresh_s`;
    - stamp `_config_read_at` when reading;
    - read inside `transaction.atomic()` (a savepoint), so a failed read never poisons a Postgres
      transaction;
    - keep today's fallbacks to `{}`.
  - `set_config`:
    - `ThemeConfig.objects.get_or_create(theme_name=self.name)`;
    - set `row.config[key] = value`;
    - `row.save(update_fields=['config', 'updated_at'])`;
    - then `invalidate_config_cache()`.
    - It must not touch `is_active`.

- [ ] **Step 4: Run them and see them pass**
  Run the same command. Expected: 4 tests OK. Then run `<env> .venv/bin/python manage.py test themes`:
  OK.

- [ ] **Step 5: Commit**
  ```bash
  git add themes/base.py themes/test_theme_config.py
  git commit -m "feat(themes): save a theme setting and re-read settings every 10 s"
  ```

### Task 2: One settings form, save and description for any target

**Files:**
- Modify: `plugins/config_schema.py` (add three functions)
- Modify: `plugins/installed/admin_dashboard/views_split/settings.py:43-74`. The body of
  `_build_panel_fields` becomes `return config_schema.form_fields(plugin_instance, schema)`, so its five
  callers stay untouched.
- Modify: `plugins/installed/admin_dashboard/urls.py:69-109`. The POST loop of `plugin_settings_view`
  becomes one `config_schema.save_posted(...)` call.
- Modify: `core/assistant/tools/ecommerce.py:96-150`. `settings.describe` builds its entries with
  `config_schema.describe_settings(...)`, and `_DESCRIBED_KEYWORDS` moves with it.
- Test: `plugins/tests_config_schema.py` (add a class)

**Interfaces:**
- Produces (in `plugins/config_schema.py`). A target is any object with `get_config() -> dict` and
  `set_config(key, value)`; a plugin and a theme both qualify.
  - `form_fields(target, schema: dict) -> list[dict]`: today's `_build_panel_fields` body, the same dict
    keys.
  - `save_posted(target, schema: dict, post, *, ajax: bool) -> list[str]`:
    - today's loop, the same rules: an absent boolean is saved as off only when `ajax` or the key is in
      `post.getlist('_booleans')`;
    - a blank or masked secret is skipped;
    - a value `coerce` refuses is skipped.
    - Returns the saved keys in schema order.
  - `describe_settings(props: dict, config: dict) -> list[dict]`: today's `settings.describe` entry shape
    (`key, title, description, type, default, value, stored, secret, agent_writable` plus the described
    keywords).

- [ ] **Step 1: Write the failing test.** Add `TargetAgnosticTests` to `plugins/tests_config_schema.py`.
  - The target is a stub class with `get_config()` returning a dict and `set_config` recording calls.
  - Its schema has `title` (string), `count` (integer), `on_sale` (boolean) and `api_key` (string,
    `format: password`).
  - `test_save_posted_writes_through_any_target`:
    - post: `QueryDict('title=x&count=abc&api_key=&_booleans=on_sale')`, `ajax=False`;
    - expect `saved == ['title', 'on_sale']`;
    - expect the stub recorded `[('title', 'x'), ('on_sale', False)]`.
  - `test_form_fields_reads_the_targets_config`: config `{'title': 'Stored'}` gives the `title` field
    `value == 'Stored'`, and the `api_key` field `value == ''`.
  - `test_describe_settings_marks_secrets_and_stored_values`:
    - `api_key` has `secret is True`;
    - `title` has `stored is True` and `agent_writable is True`.

- [ ] **Step 2: Run it and see it fail**
  Run: `<env> .venv/bin/python manage.py test plugins.tests_config_schema -v 2`
  Expected: FAIL (`AttributeError: module 'plugins.config_schema' has no attribute 'save_posted'`).

- [ ] **Step 3: Move the three bodies** into `plugins/config_schema.py` and point the three callers at
  them. Change no behaviour.

- [ ] **Step 4: Run the new and the existing tests**
  Run:
  ```bash
  <env> .venv/bin/python manage.py test plugins.tests_config_schema \
    plugins.installed.admin_dashboard.tests.test_settings_save_by_schema \
    plugins.installed.admin_dashboard.tests.test_settings_secret_masking \
    core.assistant.tests.test_admin_ops plugins.installed.reviews.tests.test_trust_strip
  ```
  Expected: all OK.

- [ ] **Step 5: Commit**
  ```bash
  git add plugins/config_schema.py plugins/tests_config_schema.py \
    plugins/installed/admin_dashboard/views_split/settings.py plugins/installed/admin_dashboard/urls.py \
    core/assistant/tools/ecommerce.py
  git commit -m "refactor: one settings form, save and description for apps and themes"
  ```

### Task 3: The Theme card under Settings → Storefront

**Files:**
- Create: `plugins/installed/storefront/theme_settings.py` (the view)
- Modify: `plugins/installed/storefront/app.py` (add `contribute_dashboard_pages`)
- Modify: `plugins/installed/admin_dashboard/templates/admin_dashboard/plugin_settings.html`. The
  `{% empty %}` line becomes `{{ empty_text|default:"This app doesn't expose any settings." }}`.
- Test: `plugins/installed/storefront/tests/test_theme_settings_page.py` (create)

**Interfaces:**
- Consumes: `MorpheusTheme.set_config` (Task 1), `config_schema.form_fields` and
  `config_schema.save_posted` (Task 2).
- Produces:
  - `theme_settings(request) -> HttpResponse` in `plugins/installed/storefront/theme_settings.py`;
  - `DashboardPage(slug='theme', label='Theme', section='storefront', nav='settings', icon='palette',
    view='plugins.installed.storefront.theme_settings.theme_settings', hint='Settings your active theme
    offers', order=20)`, served at `/dashboard/apps/storefront/theme/`.

- [ ] **Step 1: Write the failing tests** in `test_theme_settings_page.py`.
  - Sign in a superuser with `force_login`.
  - Call `addCleanup(theme_registry.active.invalidate_config_cache)`.
  - Tests:
    - `test_the_storefront_settings_list_the_theme_card`: GET `/dashboard/settings/storefront/` contains
      `href="/dashboard/apps/storefront/theme/"` and `Settings your active theme offers`.
    - `test_the_page_shows_the_active_themes_settings`: GET `/dashboard/apps/storefront/theme/` is 200 and
      contains `Theme: dot books — modern bookstore` and `name="tagline"`.
    - `test_saving_changes_the_theme_setting`: POST `{'tagline': 'A new line'}` redirects, and
      `theme_registry.active.get_config_value('tagline') == 'A new line'`.
    - `test_an_unticked_switch_turns_off_only_when_the_form_showed_it`:
      - Patch the active theme's `get_config_schema` to add `show_bar` (boolean, default True), and store
        `show_bar=True`.
      - POST `{'tagline': 'x'}`: `show_bar` stays True.
      - POST `{'tagline': 'x', '_booleans': 'show_bar'}`: `show_bar` is False.
    - `test_a_theme_with_no_settings_says_so`: with the schema patched to `{}`, the page contains
      `The active theme, dot books — modern bookstore, has no settings.`
    - Permission boundary, following the `permission-boundary-tests` skill and the existing rbac-enforce
      test pattern:
      - `test_anonymous_is_sent_to_sign_in` (302);
      - `test_staff_without_system_write_is_refused_while_rbac_enforces` (403);
      - `test_a_superuser_gets_the_page` (200).

- [ ] **Step 2: Run them and see them fail**
  Run: `<env> .venv/bin/python manage.py test plugins.installed.storefront.tests.test_theme_settings_page -v 2`
  Expected: FAIL (404 on `/dashboard/apps/storefront/theme/`).

- [ ] **Step 3: Implement the view and the contribution.**
  - With no active theme, raise `Http404('No active theme.')`.
  - **POST:**
    - `saved = config_schema.save_posted(theme, schema, request.POST, ajax=<X-Requested-With is
      XMLHttpRequest>)`;
    - AJAX gets `JsonResponse({'ok': True, 'saved': saved})`;
    - otherwise redirect to `request.path`.
  - **GET:** render `admin_dashboard/plugin_settings.html` with:
    - `panel = {'label': f'Theme: {theme.label}', 'description': theme.description}`;
    - `plugin_name = 'theme'`;
    - `fields = config_schema.form_fields(theme, schema)`;
    - `empty_text` (Global Constraints copy);
    - `active_nav = 'settings'`;
    - the trail Dashboard › Settings (`/dashboard/settings/`) › Storefront (`/dashboard/settings/storefront/`)
      › Theme.

- [ ] **Step 4: Run them and the shell's guards**
  Run:
  ```bash
  <env> .venv/bin/python manage.py test plugins.installed.storefront.tests.test_theme_settings_page \
    plugins.installed.admin_dashboard.tests.test_navigation \
    plugins.installed.admin_dashboard.tests.test_disable_guards \
    plugins.installed.admin_dashboard.tests.test_dashboard_search
  ```
  Expected: all OK. `test_navigation` now also opens the new tool.

- [ ] **Step 5: Commit**
  ```bash
  git add plugins/installed/storefront/theme_settings.py plugins/installed/storefront/app.py \
    plugins/installed/storefront/tests/test_theme_settings_page.py \
    plugins/installed/admin_dashboard/templates/admin_dashboard/plugin_settings.html
  git commit -m "feat(storefront): a Theme card under Settings, Storefront edits the active theme's settings"
  ```

### Task 4: Linda reads and changes the active theme's settings

**Files:**
- Modify: `core/assistant/tools/admin_ops.py`. Add `theme_describe_tool` and `theme_set_tool` after
  `theme_activate_tool`.
- Modify: `core/assistant/tools/__init__.py`. Import both and list them after `theme_activate_tool` in
  `get_default_tools()`.
- Test: `core/assistant/tests/test_theme_tools.py` (create)

**Interfaces:**
- Consumes: `MorpheusTheme.set_config` (Task 1), `config_schema.describe_settings`,
  `config_schema.clean` and `config_schema.agent_writable` (Task 2 and existing).
- Produces:
  - **`theme.describe`:** no arguments; scopes `['system.read']`.
    - Output: `{'theme': name, 'label': label, 'settings': [...]}`.
    - With no active theme: `{'theme': None, 'label': '', 'settings': []}` and display `No active theme.`
  - **`theme.set`:** `key: str`, `value: str`, `confirmed: bool = False`; scopes `['system.write']`;
    `requires_approval=True`.
    - Output: `{'theme', 'key', 'value'}`.
    - Errors: `ToolError` ending in `Nothing was changed.`
  - **Descriptions:**
    - `theme.describe`: "Describe the active storefront theme's settings (read-only): for each, its
      type, allowed values, default and current value, and whether you may change it with theme.set."
    - `theme.set`: "Change one setting of the active storefront theme: pass `key` and `value` as text,
      read and checked against the setting's type. theme.describe lists them. confirmed=True after the
      user approves."

- [ ] **Step 1: Write the failing tests** in `test_theme_tools.py` (`TestCase`, cleanup as in Task 1).
  - `test_describe_lists_the_active_themes_settings`:
    - `output['theme'] == theme.name`;
    - the `tagline` entry has `default == 'a quieter shelf for louder books'` and
      `agent_writable is True`.
  - `test_set_needs_the_merchants_yes`: no `confirmed` raises `ToolError`, and the stored value is
    unchanged.
  - `test_set_changes_the_setting`: `{'key': 'tagline', 'value': 'Hi', 'confirmed': True}` gives
    `theme.get_config_value('tagline') == 'Hi'`.
  - `test_set_refuses_an_unknown_key`: `ToolError` whose message ends in `Nothing was changed.`, and no
    `ThemeConfig` row is created.
  - `test_set_refuses_a_value_of_the_wrong_type`: patch the schema with `columns` (integer); `'abc'` is
    refused, and nothing is stored.
  - `test_set_refuses_a_key_only_the_merchant_may_change`: patch with `x-agent-writable: False`;
    refused.
  - `test_set_needs_approval_and_both_are_lindas`:
    - `theme_set_tool.requires_approval is True`;
    - both names are in `[t.name for t in get_default_tools()]`.

- [ ] **Step 2: Run them and see them fail**
  Run: `<env> .venv/bin/python manage.py test core.assistant.tests.test_theme_tools -v 2`
  Expected: FAIL (`ImportError: cannot import name 'theme_describe_tool'`).

- [ ] **Step 3: Implement both tools**, mirroring `settings_set_tool`.
  - Call `_require_confirmed(confirmed)` first.
  - Find the property in `theme.get_config_schema().get('properties') or {}`. An unknown key is refused:
    themes have no legacy undeclared settings.
  - Then check `agent_writable`.
  - Then `clean`, catching `SettingError` as a `ToolError`.
  - Then `set_config`.

- [ ] **Step 4: Run them and Linda's guards**
  Run:
  ```bash
  <env> .venv/bin/python manage.py test core.assistant.tests.test_theme_tools core.assistant \
    plugins.installed.agent_mcp.tests.test_linda_turn core.agents.tests.test_registry_collisions
  ```
  Expected: all OK.

- [ ] **Step 5: Commit**
  ```bash
  git add core/assistant/tools/admin_ops.py core/assistant/tools/__init__.py core/assistant/tests/test_theme_tools.py
  git commit -m "feat(linda): theme.describe and theme.set for the active theme's settings"
  ```

### Task 5: Guides, docs and the release

**Files:**
- Modify: `plugins/installed/storefront/help.md`. Add one "Common tasks" bullet, plain words, no
  developer terms: "Change the wording and pictures your theme offers, such as a notice or the home
  banner, on [Theme](page:theme) in Settings, Storefront. Linda can change them too, once you say yes."
- Modify: `docs/THEME_DEVELOPMENT.md` §9:
  - replace "the dashboard renders this schema as a form" with the page's place;
  - document `set_config`, the 10-second re-read and Linda's two tools.
- Modify: `docs/superpowers/specs/2026-11-21-theme-settings-and-christmas-design.md`: the URL and card
  label per the Rulings above.
- Modify (only where they already list `theme.activate`): `docs/MCP_SERVER.md` and
  `docs/MORPHEUS_API.md`. Grep first; add the two tools beside it.
- Release: `morph/settings.py` and `docs/RELEASE_NOTES.md` via the release command.

- [ ] **Step 1: Write the docs above.** Then run the help guards:
  `<env> .venv/bin/python manage.py test plugins.installed.release_notes`. Expected: OK (the marker
  `page:theme` resolves; no developer words).

- [ ] **Step 2: Cut the release**
  ```bash
  <env> .venv/bin/python manage.py release --minor "Theme settings on the dashboard" \
    -m "Settings, Storefront has a Theme card: the active theme's own settings (a notice, the home banner and the like), saved like any other settings card." \
    -m "Linda can read them (theme.describe) and change one once you say yes (theme.set)." \
    -m "A saved theme setting reaches every server within 10 seconds; before, a change made outside a restart reached only one."
  ```
  Expected: the version is v0.185.0 and a dated entry appears.

- [ ] **Step 3: Run the gates**
  ```bash
  .venv/bin/ruff check . && .venv/bin/ruff format --check .
  <env> .venv/bin/python manage.py check && <env> .venv/bin/python manage.py makemigrations --check --dry-run
  .venv/bin/python scripts/check_core_boundary.py && .venv/bin/python scripts/check_plugin_boundary.py && .venv/bin/python scripts/check_plugin_standard.py
  <env> .venv/bin/python manage.py release --check
  ```
  Expected: all pass.

- [ ] **Step 4: Run the wide suite** with all five opt-in apps:
  `MORPHEUS_EXTRA_APPS=plugins.installed.booking_marketplace,plugins.installed.dsers,plugins.installed.zendrop,plugins.installed.cjdropshipping,plugins.installed.aliexpress`
  on `themes plugins core api`. Expected: no failures beyond those `main` already has.

- [ ] **Step 5: Commit**
  ```bash
  git add plugins/installed/storefront/help.md docs/THEME_DEVELOPMENT.md \
    docs/superpowers/specs/2026-11-21-theme-settings-and-christmas-design.md morph/settings.py docs/RELEASE_NOTES.md
  git commit -m "docs: theme settings page; release v0.185.0"
  ```
  Add `docs/MCP_SERVER.md` and `docs/MORPHEUS_API.md` to the `git add` only if Step 1 changed them.
