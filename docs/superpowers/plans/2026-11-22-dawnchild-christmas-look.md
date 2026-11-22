# Dawnchild Christmas Look Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Christmas look to Dawnchild as a theme setting, plus two footer fixes, released as v0.186.0. The setting is off by default, runs between two days every year, or is on for a preview.

**Architecture:**
- Three settings in Dawnchild's `get_config_schema()`, read by a small pure module, `themes/library/dawnchild/christmas.py`.
- The theme object gets a `christmas_on()` method. Templates already receive the theme as `active_theme`, so `{% if active_theme.christmas_on %}` gates every piece.
- The pieces live in Dawnchild's own includes, one stylesheet (`christmas.css`) and one deferred script (`christmas.js`). Header decorations are CSS on existing markup.
- Release 1 (v0.185.0, live) already gives the merchant the Theme card and Linda `theme.describe` / `theme.set`, so nothing new is needed there.

**Tech Stack:** Django templates, plain CSS, vanilla JS (canvas, IntersectionObserver, MutationObserver), Django `TestCase` / `SimpleTestCase`.

**Spec:** `docs/superpowers/specs/2026-11-21-theme-settings-and-christmas-design.md` (release 2). The look is the throwaway spike the owner approved on 2026-11-21. Its two files are references for motion and shapes only, never shipped:
- `/private/tmp/claude-502/-Users-magnetoid-coding-morph/930e2439-2180-417a-a048-65f5c54b1562/scratchpad/xmas-spike.js` (hero);
- `…/xmas-spike-extras.js` (header and footer).

## Global Constraints

- **`christmas_look`:** `off` (the default), `dates` or `on`. `on` lets the owner preview the look before the season.
- **`christmas_from`:** day and month written `DD-MM`, default `01-12` (1 December).
- **`christmas_until`:** `DD-MM`, default `06-01` (6 January).
- **The dates** apply every year, on the store's clock (`core.utils.site.store_today()`), and the range may cross New Year.
- **One stylesheet and one script.** When the look is on, the theme's own templates render the pieces from one theme stylesheet and one theme script. The script carries the CSP nonce and attaches behaviour with `addEventListener`. No inline handlers, no script without the nonce.
- **Pause.** One pause stops all the motion, both in the hero and in the footer. The choice is remembered in `localStorage`, wrapped in try/catch.
- **Reduced motion.** `prefers-reduced-motion` gets a still version: the final states, no motion.
- **The hero image (LCP) is never delayed.** The snow starts after the image loads, and it pauses when the hero is off screen or the tab is hidden.
- **Footer fixes in the same release:**
  - the newsletter field and its "Send me the letter" button become readable;
  - on phones the pines get room above the last footer link.
- **Defaults leave every store as it is today.**
- **Button copy, from the approved spike:** `Pause the snow` (while it moves) and `Let it snow` (while paused).

## Rulings (where the plan settles what the spec leaves open)

- **Two buttons, one pause.** A pause button sits on the hero (home page) and one in the footer sign-off (every page). Both drive one shared paused state, so one press stops everything.
  - Why: the approved spike had both, and the hero is a screen away from the footer.
  - Cost if wrong: drop the hero button.
- **Both dates count.** 1 December and 6 January are both inside the default range.
- **A stored date that is not a real day** ("31-02", "1 Dec", "") falls back to that bound's default, and the page never errors.
  - The dashboard form path does not validate, and that is the same for apps.
  - The schema gains a `pattern`, so Linda's `theme.set` refuses a date not written `DD-MM` (Task 1).
- **The header pieces are CSS only:** the snow ledge, the icicles and the holly sit on existing elements through pseudo-elements, so `_lockup.html` stays untouched. The basket burst is the script's.
- **`christmas.css` loads in the head.** Decoration markup that arrives before its CSS shifts the layout (CLAUDE.md's CLS landmine). Task 4 measures that the hero's LCP is no later with the look on.
- **The paused state is read before first paint.** The theme's existing inline head script (the one that adds `js` to `<html>`) also reads `localStorage['dawnchild:christmas-paused']` in try/catch, so a visitor who paused never sees a moment of motion.

## Review Focus

1. **A stored date that is not a real day** ("31-02", "1 Dec", "", "00-12"). That bound falls back to its default, and pages render. Pinned in Task 1.
2. **The default range across New Year.** 30 Nov is off; 1 Dec, 31 Dec, 1 Jan and 6 Jan are on; 7 Jan is off. Pinned in Task 1.
3. **The store's clock, not UTC.** At 2026-11-30 23:30 UTC, a store in `Europe/Belgrade` (already 1 Dec) shows the look in `dates` mode. Pinned in Task 1.
4. **A payment page with the look on.** On `/cart/`, every `<script>` carries the nonce and no element has an `on…=` handler. Pinned in Task 3.
5. **No motion without a working pause.**
   - With JavaScript off, nothing animates and the pause buttons are `hidden`.
   - Under `prefers-reduced-motion: reduce`, nothing animates and both buttons stay hidden.
   - Pinned in Task 3.

---

### Task 1: The Christmas settings and the day rule

**Files:**
- Modify: `plugins/config_schema.py`:
  - `validate()` checks a string against `pattern`;
  - `_DESCRIBED_KEYWORDS` gains `'pattern': 'pattern'`.
- Create: `themes/library/dawnchild/christmas.py`
- Modify: `themes/library/dawnchild/theme.py`: three schema properties and `christmas_on()`.
- Modify: `themes/test_dawnchild.py`: `test_theme_settings_all_have_a_reader` accepts a read in the theme's own Python besides `theme.py`.
- Test: `themes/test_dawnchild_christmas.py` (create); `plugins/tests_config_schema.py`.

**Interfaces:**
- Produces:
  - `themes.library.dawnchild.christmas.parse_day(text: str) -> tuple[int, int] | None`: `'01-12'` → `(12, 1)` (month, day); anything else → `None`.
  - `themes.library.dawnchild.christmas.is_on(config: Mapping[str, Any], today: datetime.date) -> bool`.
  - `DawnchildTheme.christmas_on(self) -> bool`, which is `is_on(self.get_config(), store_today())`.
  - `config_schema.validate` refuses a string that does not `re.fullmatch` the spec's `pattern`, with the message `f'{name!r} must be written like {spec.get("examples", [spec["pattern"]])[0]}'`.

- [ ] **Step 1: Write the failing tests** in `themes/test_dawnchild_christmas.py` (`SimpleTestCase` unless noted):
  - **`test_the_default_is_off`:** `is_on({}, date(2026, 12, 25)) is False`.
  - **`test_on_shows_it_any_day`:** `is_on({'christmas_look': 'on'}, date(2026, 7, 1)) is True`.
  - **`test_dates_use_the_default_range_across_new_year`:** with `{'christmas_look': 'dates'}`:
    - 2026-11-30 → False; 2026-12-01 → True; 2026-12-31 → True;
    - 2027-01-01 → True; 2027-01-06 → True; 2027-01-07 → False.
  - **`test_dates_inside_one_year`:** `{'christmas_look': 'dates', 'christmas_from': '10-12', 'christmas_until': '24-12'}`. 2026-12-09 → False; 12-10 and 12-24 → True; 12-25 → False.
  - **`test_a_date_that_is_not_a_day_falls_back_to_its_default`:**
    - for each of `'31-02'`, `'1 Dec'`, `''`, `'00-12'`, `'12-13'`: with `christmas_from` set to it, 2026-12-01 → True and 2026-11-30 → False;
    - `parse_day('29-02') == (2, 29)`.
  - **`test_an_unknown_mode_is_off`:** `{'christmas_look': 'yes'}` on 2026-12-25 → False.
  - **`test_the_store_clock_decides_the_day`** (`TestCase`):
    - patch `core.utils.site.store_timezone` to return `ZoneInfo('Europe/Belgrade')`;
    - patch `django.utils.timezone.now` to `datetime(2026, 11, 30, 23, 30, tzinfo=UTC)`;
    - `theme_registry.get('dawnchild')` with `set_config('christmas_look', 'dates')` → `christmas_on() is True`;
    - clean up with `invalidate_config_cache`.
  - **`test_the_schema_declares_the_three_settings`:**
    - `christmas_look` has `enum == ['off', 'dates', 'on']` and `default == 'off'`;
    - `christmas_from` has default `'01-12'` and `christmas_until` default `'06-01'`;
    - both carry `pattern == r'\d{2}-\d{2}'` and `examples == ['01-12']` / `['06-01']`.
  - **`test_linda_cannot_store_a_date_not_written_dd_mm`:**
    - `config_schema.clean('christmas_from', prop, '1 Dec')` raises `SettingError` whose text contains `01-12`;
    - `clean(..., '24-12')` returns `'24-12'`.

  In `plugins/tests_config_schema.py`, add `test_a_pattern_is_checked_and_described`:
  - `validate('x', 'ab', {'type': 'string', 'pattern': r'\d+'})` is non-empty;
  - `'12'` gives `''`;
  - `describe_settings({'x': {'type': 'string', 'pattern': r'\d+'}}, {})[0]['pattern'] == r'\d+'`.

- [ ] **Step 2: Run them and see them fail**
  Run: `<env> .venv/bin/python manage.py test themes.test_dawnchild_christmas plugins.tests_config_schema -v 2`
  Expected: FAIL. `christmas` cannot be imported, the schema keys are missing, and the pattern is not checked.

- [ ] **Step 3: Implement.**
  - `parse_day` accepts exactly two digits, a hyphen and two digits. The month is 1–12. The day is 1 up to that month's length in a leap year, so 29-02 is allowed.
  - `is_on` returns True:
    - for `on`;
    - for `dates`, when `(today.month, today.day)` lies in the inclusive range, or, when `from > until`, in either end of it;
    - otherwise False.
  - Schema titles, verbatim:
    - `christmas_look`: `Christmas look: off, dates (every year between the two days below) or on (shown now, to preview it)`;
    - `christmas_from`: `Christmas look starts (day-month, DD-MM; 01-12 is 1 December)`;
    - `christmas_until`: `Christmas look ends, that day included (DD-MM; 06-01 is 6 January)`.
  - `christmas_on` imports `store_today` inside the method.
  - In `test_dawnchild.py`, the reader check passes a key that appears in `theme_config.<key>` in a template or, as a quoted word, in a `.py` file under the theme other than `theme.py`.

- [ ] **Step 4: Run them, the theme suites and the reader guard**
  Run: `<env> .venv/bin/python manage.py test themes plugins.tests_config_schema core.tests.test_settings_keys_have_readers core.assistant.tests.test_theme_tools`
  Expected: all OK.

- [ ] **Step 5: Commit**
  ```bash
  git add plugins/config_schema.py themes/library/dawnchild/christmas.py themes/library/dawnchild/theme.py themes/test_dawnchild.py themes/test_dawnchild_christmas.py plugins/tests_config_schema.py
  git commit -m "feat(dawnchild): a Christmas look setting, off, between two days every year, or on"
  ```

### Task 2: The footer letter can be read

The cause, measured live on 2026-11-22: a later rule in `dawnchild.css` gives `.site-foot` an olive background (rgb 138,127,61) and redefines `--parchment-light` and `--parchment` as `var(--ink)` inside the footer. The field (`background: var(--parchment-light); color: var(--ink)`) and compat's button (`background: var(--parchment-light); color: var(--ink)`) therefore both render ink on ink, rgb(11,14,6) on rgb(11,14,6).

**Files:**
- Modify: `themes/library/dawnchild/static/dawnchild/compat.css:243-248` (the `.site-foot .foot-letter` rules)
- Test: `themes/test_dawnchild.py` (`DawnchildFilesTests`)

- [ ] **Step 1: Write the failing test** `test_the_footer_letter_field_and_button_can_be_read`. It reads compat.css and asserts these strings are present:
  - `.site-foot .foot-letter .signup input { background: #f8f1df; color: #0b0e06; }`
  - `.site-foot .foot-letter .btn { background: #4f150f; color: #f8f1df; border-color: #4f150f; }`
  - `.site-foot .foot-letter .btn:hover { background: #0b0e06; color: #f8f1df; }`

  The field becomes cream with ink text, the colours the shop's other buttons already use. The button becomes bordeaux with cream text.
- [ ] **Step 2: Run it.** `<env> .venv/bin/python manage.py test themes.test_dawnchild.DawnchildFilesTests`. Expected: FAIL.
- [ ] **Step 3: Replace the input, button and hover rules** in compat.css with the three above. Leave the label, status and sign-off rules as they are.
- [ ] **Step 4: Run it.** Expected: OK.
- [ ] **Step 5: Commit**
  ```bash
  git add themes/library/dawnchild/static/dawnchild/compat.css themes/test_dawnchild.py
  git commit -m "fix(dawnchild): the footer's letter field and button are readable on the olive footer"
  ```

### Task 3: The look: markup, stylesheet and script

**Files:**
- Create:
  - `themes/library/dawnchild/templates/storefront/_christmas_hero.html`
  - `themes/library/dawnchild/templates/storefront/_christmas_footer.html`
  - `themes/library/dawnchild/templates/storefront/_christmas_pause.html` (the button, included twice)
  - `themes/library/dawnchild/static/dawnchild/christmas.css`
  - `themes/library/dawnchild/static/dawnchild/christmas.js`
- Modify `themes/library/dawnchild/templates/storefront/base.html`:
  - the head link;
  - the early head script reads the paused state;
  - `data-christmas` on `<body>`;
  - the footer include;
  - the pause button in `.foot-signoff`;
  - the script tag after `dawnchild.js`.
- Modify `themes/library/dawnchild/templates/storefront/home.html`: the hero include inside `#home-banner`; the cap inside `.hw-plaque`.
- Modify `themes/test_dawnchild.py`: add the three new templates to `OWN_TEMPLATES`.
- Test: `themes/test_dawnchild_christmas.py`

**Interfaces:**
- Consumes: `active_theme.christmas_on` (Task 1).
- Produces (the markers the script and the tests share):
  - `<body … data-christmas>`, only while it is on;
  - in the head, after dawnchild.css: `<link rel="stylesheet" href="{% static 'dawnchild/christmas.css' %}">`;
  - after the dawnchild.js tag: `<script nonce="{{ csp_nonce }}" src="{% static 'dawnchild/christmas.js' %}" defer></script>`;
  - **hero** (`aria-hidden="true"` on every decoration): `data-xmas="hero"`, which holds:
    - `<canvas data-xmas-snow="hero">`,
    - `data-xmas="garland"` (twinkling lights),
    - `data-xmas="frost"` (corner feathers),
    - `data-xmas="drift"`;
  - `data-xmas="cap"` inside `.hw-plaque`;
  - **footer:** `data-xmas="scenery"` standing on the `.foot-signoff` line. It holds:
    - pines;
    - a cottage with `data-xmas="window"` (flicker) and `data-xmas="smoke"`;
    - `<canvas data-xmas-snow="footer">`.

    Next to the newsletter label sits `data-xmas="letter"`; it gets the class `fly` on the footer form's `submit`. The letter sits inside base.html's `{% if has_newsletter %}` block, so it appears only with the form, and the tests run with the newsletter app on, as in the default app list.
  - **Pause button:** `<button type="button" class="xmas-pause" data-xmas-pause aria-pressed="false" hidden data-label-pause="{% translate 'Pause the snow' %}" data-label-play="{% translate 'Let it snow' %}" aria-label="{% translate 'Pause the snow' %}">`. Both icons are inline SVGs, and CSS shows one by `aria-pressed`.
  - **Paused state:** `<html data-christmas-paused>` while paused; the stored value is `localStorage['dawnchild:christmas-paused'] === '1'`.

- [ ] **Step 1: Write the failing tests** in `themes/test_dawnchild_christmas.py`. Use `_Dawnchild` from `themes.test_dawnchild` (it activates the theme), and set `christmas_look` through `theme_registry.get('dawnchild').set_config`.
  - **`test_off_renders_nothing_of_it`** (the default):
    - `/` and `/products/` have no `data-christmas`, no `christmas.css`, no `christmas.js` and no `data-xmas`.
  - **`test_on_renders_every_piece_on_the_home_page`:** on `/`:
    - the head link sits before `</head>`;
    - the nonce'd script tag is present;
    - body has `data-christmas`;
    - each of `data-xmas="hero"`, `garland`, `frost`, `drift`, `cap`, `scenery`, `window`, `smoke` and `letter` appears once;
    - both canvases are there;
    - `data-xmas="cap"` sits between `class="hw-plaque"` and the plaque's closing `</h2>`;
    - two pause buttons, each `hidden` and `aria-pressed="false"`, labelled `Pause the snow` / `Let it snow`.
  - **`test_on_other_pages_has_the_footer_and_header_but_no_hero`:** `/products/` has `data-christmas`, the scenery and one pause button, and no `data-xmas="hero"`.
  - **`test_dates_mode_follows_the_store_day`:**
    - `christmas_look='dates'`, with `core.utils.site.store_today` patched to return 2026-12-15: `/` has `data-christmas`;
    - patched to 2026-11-15: it has none.
    - `christmas_on` imports `store_today` inside the method, so this patch target reaches it.
  - **`test_the_basket_under_the_look_keeps_the_payment_page_policy`:** with it on, `/cart/`:
    - every `<script` tag carries `nonce="`;
    - `re.search(r'\son[a-z]+\s*=\s*["\']', body)` is None.
  - **`test_the_stylesheet_holds_still_without_script_or_with_reduced_motion`** (`SimpleTestCase`, reading christmas.css):
    - every `animation:` declaration sits inside a rule whose selector starts with `.js [data-christmas]`;
    - the file has `@media (prefers-reduced-motion: reduce)`, which sets `animation: none` and hides `[data-xmas-snow]` and `.xmas-pause`;
    - `[data-christmas-paused]` rules set `animation-play-state: paused`;
    - an `@media (max-width: 600px)` rule pads `.foot-inner` at the bottom.
  - **`test_the_script_waits_for_the_picture_and_stops_when_unseen`** (`SimpleTestCase`, reading christmas.js). It contains:
    - `addEventListener`, `IntersectionObserver`, `visibilitychange`, `MutationObserver`;
    - `prefers-reduced-motion`;
    - `dawnchild:christmas-paused`, appearing only inside `try {` blocks;
    - `.complete`, the hero image check before the snow starts.

    It contains none of `innerHTML`, `eval(`, `document.write`, `onclick`.
  - In `test_dawnchild.py`, `OWN_TEMPLATES` gains the three new template names, so the existing nonce and handler test covers them.

- [ ] **Step 2: Run them and see them fail**
  Run: `<env> .venv/bin/python manage.py test themes.test_dawnchild_christmas themes.test_dawnchild -v 2`
  Expected: FAIL (no markup, no files).

- [ ] **Step 3: Build the pieces.**
  - **Shapes and motion** follow the spike files: three snow depths with gusts, a twinkling garland, frost feathers, a growing cap, a drift, the header ledge with icicles and holly, a basket burst on a rising `#cart-badge` count, the pines and cottage with a flickering window and rising smoke, footer snow, a cap on the footer wordmark, and a letter that flies.
  - **The script, `christmas.js`:**
    - it does nothing unless `document.body.hasAttribute('data-christmas')`;
    - it does nothing under `matchMedia('(prefers-reduced-motion: reduce)')`;
    - it removes `hidden` from the pause buttons;
    - it starts the hero snow only once `#home-banner img` is `.complete` (or on its `load`), or at once on a banner with no picture;
    - it runs one `requestAnimationFrame` loop per canvas, stopped while paused, off screen (IntersectionObserver) or `document.hidden`;
    - a click on either button toggles the shared state, updates `aria-pressed`, the label and `<html data-christmas-paused>`, and saves it in try/catch;
    - it builds nodes with `createElement` and `textContent`, never `innerHTML`.
  - **The stylesheet, `christmas.css`:**
    - animations run only under `.js [data-christmas]`;
    - `[data-christmas-paused]` pauses them;
    - reduced motion shows the final states (full cap, drift, frost, lit garland) and hides the canvases and buttons;
    - at `max-width: 600px`, `.foot-inner` gets bottom padding equal to the scenery's height, so the pines clear the last footer link.
    - Never write `*/` inside a comment.
  - **The head script** gains the try/catch read of the paused state.

- [ ] **Step 4: Run them and every theme suite**
  Run: `<env> .venv/bin/python manage.py test themes core.tests.test_css_comments core.tests.test_payment_page_csp`
  Expected: all OK.

- [ ] **Step 5: Commit**
  ```bash
  git add themes/library/dawnchild/templates/storefront/_christmas_hero.html themes/library/dawnchild/templates/storefront/_christmas_footer.html themes/library/dawnchild/templates/storefront/_christmas_pause.html themes/library/dawnchild/static/dawnchild/christmas.css themes/library/dawnchild/static/dawnchild/christmas.js themes/library/dawnchild/templates/storefront/base.html themes/library/dawnchild/templates/storefront/home.html themes/test_dawnchild.py themes/test_dawnchild_christmas.py
  git commit -m "feat(dawnchild): the Christmas look on the hero, header and footer, with one pause"
  ```

### Task 4: See it in a browser, then release

**Files:**
- Modify: `/Users/magnetoid/coding/morph/.claude/launch.json`. Add a `dawnchild-local` configuration:
  - command: `.venv/bin/python manage.py runserver 127.0.0.1:8781`;
  - working directory: the worktree;
  - env: `DEBUG=True`, `DATABASE_URL=sqlite:////private/tmp/claude-502/-Users-magnetoid-coding-morph/930e2439-2180-417a-a048-65f5c54b1562/scratchpad/dawnchild-dev.sqlite3`, `REDIS_URL=redis://127.0.0.1:6379/15`, `MORPHEUS_ACTIVE_THEME=dawnchild`, `SECRET_KEY=local-preview`.
  - Use `runtimeExecutable` `/usr/bin/env`, with these settings as arguments before the command.
- Release: `morph/settings.py`, `docs/RELEASE_NOTES.md` through the release command.

- [ ] **Step 1: Turn the look on locally and check it**
  - Migrate the dev DB if needed, start the preview, and set `christmas_look` to `on` on the Theme card.
  - Check, recording each result:
    1. **Home at 1440×900:** every piece shows, and the console has no errors.
    2. **The pause button** stops every canvas and animation in hero and footer. After a reload it stays paused.
    3. **Reduced motion** (`matchMedia` emulation, or the CSS rule checked by computed `animation-name: none`): still, and no buttons.
    4. **LCP:** the hero image's `PerformanceObserver('largest-contentful-paint')` time with the look on is within 50 ms of off, over three throttled reloads each.
    5. **At 390×844:** the pines clear the last footer link (their `getBoundingClientRect` does not overlap it), and the footer letter field and button are readable (computed colours differ).
    6. **`/cart/`:** it renders with no CSP report in the console.
  - Then set it back to `off` and confirm nothing of it remains.
- [ ] **Step 2: Cut the release**
  ```bash
  <env> .venv/bin/python manage.py release --minor "A Christmas look for Dawnchild" \
    -m "Dawnchild has a Christmas look under Settings, Storefront, Theme: off, between two days every year (1 December to 6 January unless you change them), or on to preview it. Linda can switch it once you say yes." \
    -m "Snow, lights and frost on the home banner, a snowy ledge and holly in the header, pines and a cottage above the footer line; one button pauses all of it, and visitors who ask their device for less motion see it still." \
    -m "The footer's letter field and its button are readable again on Dawnchild's olive footer."
  ```
  Expected: v0.186.0 and a dated entry.
- [ ] **Step 3: Run the gates**
  ```bash
  .venv/bin/ruff check . && .venv/bin/ruff format --check .
  <env> .venv/bin/python manage.py check && <env> .venv/bin/python manage.py makemigrations --check --dry-run
  .venv/bin/python scripts/check_core_boundary.py && .venv/bin/python scripts/check_plugin_boundary.py && .venv/bin/python scripts/check_plugin_standard.py && .venv/bin/python scripts/check_agent_coverage.py
  <env> .venv/bin/python manage.py release --check
  ```
  Expected: all pass.
- [ ] **Step 4: Run the wide suite**
  - Use `MORPHEUS_EXTRA_APPS` with all five opt-in apps on `themes plugins core api`.
  - Expected: no failures beyond main's four order-dependent ones, recorded on 2026-11-22:
    - `book_product` `EditionHreflangHeadTests`;
    - three `seo` `MarketAlternateTests`.
- [ ] **Step 5: Commit**
  ```bash
  git add morph/settings.py docs/RELEASE_NOTES.md
  git commit -m "release: v0.186.0 A Christmas look for Dawnchild"
  ```

`<env>` = `DEBUG=True DATABASE_URL='sqlite:///:memory:' SECRET_KEY=test-key REDIS_URL=redis://127.0.0.1:6379/15`
