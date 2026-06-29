# Linda per-page AI helper ("AI-assisted tips & help")

**Status:** approved design, pre-implementation · **Date:** 2026-06-29 · **Owner:** core.assistant

Replaces the **"Guided UX & Micro-animations"** dashboard setting with an opt-in
feature: when enabled, **Linda** appears as a per-page helper card that explains
the current page and the numbers on it, and advises what to do next. Micro-
animations are decoupled from the toggle and become always-on.

## Goal / success criteria

- Toggle **on** → every dashboard page renders a Linda card built from what's
  actually on that page (the visible numbers/text), with: what the page shows,
  what the numbers mean, what to do next.
- Toggle **off** → no card; micro-animations still work.
- Revisiting a page (unchanged data) is **instant and free** (cached).
- Endpoint is staff-only and returns JSON on success **and** failure.
- Additive boolean migration + clean RemoveField — Postgres-safe.

## Decisions (locked)

- **Page sensing:** client extracts DOM text/numbers from `#main-content`, plus
  structured JSON a page may opt to emit; no screenshots / vision model.
- **Timing:** proactive on page load, **cached** (server LLM cache + client
  `sessionStorage` by signature).
- **Animations:** always-on (decoupled from the setting).
- **Toggle default:** **OFF** (opt-in — it spends LLM tokens).
- **Placement:** inline collapsible card inside `<main>`, above page content.

## Components

### 1. Setting — `core` + `admin_dashboard`
- Add `StoreSettings.ai_page_help = BooleanField(default=False)` in
  [core/models.py](../../core/models.py) + migration (additive).
- Remove `StoreSettings.guided_ux_mode` (clean `RemoveField` migration) — it no
  longer drives anything.
- [admin_dashboard/forms/settings.py](../../plugins/installed/admin_dashboard/forms/settings.py):
  drop the `guided_ux_mode` form field; add `ai_page_help`
  (label **"AI-assisted tips & help"**, help: *"Show Linda on every dashboard
  page to explain what you're looking at and advise what to do. Uses your
  configured AI provider."*).
- Remove the `get_guided_ux_mode` templatetag in
  [morph_dashboard.py](../../plugins/installed/admin_dashboard/templatetags/morph_dashboard.py);
  add `get_ai_page_help` (same safe-fallback shape, default **False**).

### 2. Animations always-on — `admin_dashboard`
- [base.html:887-888](../../plugins/installed/admin_dashboard/templates/admin_dashboard/base.html):
  drop `{% get_guided_ux_mode as guided_ux %}` and the `{% if guided_ux %}`
  gate so `<body>` always carries `guided-ux`.

### 3. Helper card partial — `core.assistant`
- New `core/assistant/templates/assistant/_page_helper.html`, **included inside
  `#main-content`, above `{% block content %}`** in base.html, gated by
  `{% get_ai_page_help %}`.
  - Because htmx-boost swaps `#main-content` (hx-target/hx-select), the card sits
    inside it and re-renders on every navigation. Its init JS must run on initial
    load **and** on `htmx:afterSwap` (mirror how `lucide.createIcons()` is re-run).
  - Markup: Linda avatar (`static 'assistant/linda-avatar.jpg'`) + title
    "Linda's take on this page" + three sections — **What this page shows**,
    **What the numbers mean**, **What to do next**. Collapsible (state in
    `localStorage`); shimmer placeholder while loading. Uses `.card` tokens.

### 4. Sensing + data flow — JS in the partial
1. On init (if enabled): collect `page_url` (path), `page_title`, `active_nav`,
   a trimmed innerText snapshot of `#main-content` (cap ~4 KB), and any
   `<script type="application/json" id="page-context">` JSON the page emitted.
   Strip email-like tokens (light PII trim).
2. `signature = path + '|' + hash(extracted numbers/text)`.
3. If `sessionStorage['linda-help:'+signature]` exists → render instantly.
4. Else `POST /dashboard/assistant/page-help/` with the context; on success cache
   in `sessionStorage` and render; on error show a quiet inline fallback.

### 5. Endpoint + service — `core.assistant`
- `core/assistant/page_help.py`: `build_page_help(context: dict) -> dict` —
  composes a focused Linda prompt and calls the provider for **structured JSON**
  `{summary: str, numbers: [{label, reading}], actions: [str]}`. Parse with the
  existing JSON-repair util (malformed-model-output landmine). Persona = Linda's
  brand voice; concise, merchant-friendly.
- `views.assistant_page_help` (POST) in
  [core/assistant/views.py](../../core/assistant/views.py) + route
  `path('page-help/', views.assistant_page_help, name='page_help')` next to
  `invoke/`/`stream/` in [core/assistant/urls.py](../../core/assistant/urls.py).
  Staff-only; **always returns JSON** (success and error).
- Caching: rely on the built-in 1h LLM cache ([llm.py:75](../../core/agents/llm.py#L75))
  — the prompt is deterministic per (page, data signature), so repeats hit cache.
  Skip the LLM entirely when the extracted text is trivially small (empty page).

## Error handling
- Provider down → circuit breaker returns a friendly note; endpoint still 200s
  with `{ok: false, message}`; card shows a quiet "Linda's unavailable right now".
- Malformed JSON → repaired; if still bad, return `{ok:false}` (no crash).
- Toggle off or non-staff → card not rendered / endpoint denied.

## Testing
- `DATABASE_URL='sqlite:///:memory:'` suite under `core/assistant/tests/`:
  - `build_page_help` returns the structured dict from a mocked provider; JSON
    repair path covered.
  - View: returns JSON on success **and** on provider error (AJAX-JSON contract).
  - **3 permission-boundary tests**: anonymous blocked, authed-without-staff
    blocked, staff allowed.
  - Template: card absent when `ai_page_help` off, present when on.
- `makemigrations --check` clean; migrations apply on Postgres (CI gate).

## Ownership / boundaries
- `core.assistant` owns endpoint, prompt/service, card partial (mirrors the
  existing `_floating_widget.html` injection).
- `admin_dashboard` owns only: the settings-form row, the `get_ai_page_help`
  tag, the one-line `{% include %}`, and the animations decoupling.
- No plugin→plugin imports. Pages enrich Linda only by *optionally* emitting the
  `#page-context` JSON — never by importing the assistant.

## Out of scope (YAGNI)
- Vision/screenshot sensing; per-page bespoke prompts; multi-language copy;
  rewriting every page to emit structured context (DOM text is the baseline;
  only `home` emits structured JSON in v1).
