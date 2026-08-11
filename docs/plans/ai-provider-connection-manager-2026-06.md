# AI provider connection manager + DeepSeek

**Status:** SHIPPED (v0.2.11, in place) · **Date:** 2026-06-30 · **Owner:** ai_assistant

> **Update (shipped):** built **in place** in `admin_dashboard` — connection
> manager + DeepSeek. The proposed relocation into `ai_assistant` was
> **dropped** (owner: not needed). The panel stays where it is; the
> "Relocate ownership" decision and the Boundary section below are **not
> pursued** and kept only as historical context.

Replace the always-show-every-provider "AI providers" panel with a
**connection manager**: by default only *connected* providers appear; an
**"Add AI"** button opens a picker of the remaining provider templates, and
connecting one reveals its form and moves it into the connected list. Also add
**DeepSeek** as a first-class provider.

## Goal / success criteria

- Panel shows **only connected providers** (api key set; Ollama counts as
  connectable without a key) as cards — no unused providers cluttering the page.
- An **"Add AI"** button opens a picker listing only **not-yet-connected**
  templates. Picking one shows its connect form (key / base URL / model);
  saving it makes the card appear in the connected list and **drops it from the
  picker**.
- A connected provider can be **disconnected** (clears its key fields → card
  leaves the list, template returns to the picker).
- **DeepSeek** is selectable, connectable, and usable by Linda/agents end-to-end.
- Disabling the `ai_assistant` plugin makes the whole panel disappear
  (disable-test) — no provider code left in `admin_dashboard`.
- Secrets stay write-only (`format: password` masking preserved).

## Decisions (locked)

- **Full connection-manager UX** (per owner) — not a lighter collapse.
- **Design-first**: this spec → approval → build.
- ~~**Relocate ownership into `ai_assistant`**~~ — **dropped (not needed).**
  Built in place in `admin_dashboard`. Original rationale kept below for history. We're rewriting the
  panel anyway; doing it in the correct layer is ~the same work and repays the
  existing debt + passes the disable test.
- **No new model.** "Connected" is derived state: `bool(<slug>_api_key)` (or
  `api_key_optional` for Ollama), read from `PluginConfig.config`. Active
  provider stays `ai_provider`.

## Components

### 1. DeepSeek provider (mirrors apikey/packy/hermes — proven pattern)
- `core/agents/provider_registry.py`: add `'deepseek'` to `_DEFAULT_BASE_URLS`
  (`https://api.deepseek.com`), `_DEFAULT_MODELS` (`deepseek-chat`),
  `_ENV_KEYS` (`DEEPSEEK_API_KEY`), and the base-url env key.
- `core/agents/llm.py`: `DeepSeekProvider(OpenAIProvider)` (OpenAI-compatible) +
  register `'deepseek'` in `_PROVIDER_CLASSES`.
- `ai_assistant/app.py`: `deepseek_api_key` (password) / `deepseek_base_url`
  / `deepseek_model` schema fields; add `'deepseek'` to the `ai_provider` enum;
  update the panel description.
- Add DeepSeek to the provider **catalog** (below).

### 2. Provider catalog → owned by `ai_assistant`
- Move `_AI_PROVIDERS` (today in `admin_dashboard/views_split/settings.py`) into
  `ai_assistant` as the single source of provider metadata
  `{slug, label, fields, defaults, docs_url, api_key_optional}`. The catalog
  already exists; this relocates it to its owner and adds DeepSeek.

### 3. Panel relocation + redesign — `ai_assistant`
- `ai_assistant` serves its own AI-providers page via `register_urls()` (the
  documented escape hatch) with its own view + template; **remove** the
  hardcoded `'ai'` category override + `settings_ai` view + `settings_ai.html`
  + `_AI_PROVIDERS` from `admin_dashboard`. The `contribute_settings_panel`
  entry points the nav at the plugin's URL.
- Template (evolve the existing card UI):
  - **Active banner** (which provider Linda uses now + resolved model) — keep.
  - **Connected list**: one card per connected provider — model, status pill,
    "Used N min ago", **Set active** / **Edit** / **Disconnect**.
  - **"Add AI"** button → picker (inline panel or `<dialog>`) listing only
    unconnected templates; selecting one reveals its connect form (key / base
    URL / model) posting to the save endpoint; on success the card joins the
    connected list. Inline JS only (CSP allows `'unsafe-inline'`; no new CDN).

### 4. Save / connect / disconnect flow
- Reuse the per-card `data-ajax` POST → `{ok, saved}` JSON contract (success
  **and** error) so the dashboard never shows a false "Saved".
- **Connect/Edit**: existing masked-password save (blank/`********` preserves
  the stored key).
- **Disconnect**: posts empty `<slug>_api_key` (+ base_url/model) to clear them;
  if the disconnected provider was active, fall back `ai_provider` to another
  connected provider or unset.

## Error handling
- No providers connected → panel shows an empty state + "Add AI" (Linda already
  surfaces "No AI provider selected" downstream — unchanged).
- Disconnecting the active provider → reassign active to a remaining connected
  provider, else clear it (UI warns Linda is now unconfigured).
- Save endpoint always returns JSON on success **and** failure.

## Boundary / ownership (torsor)
- **Fixes existing debt:** provider-specific rendering currently lives in
  `admin_dashboard` (`settings_ai` view/template + `_AI_PROVIDERS`). After this,
  `ai_assistant` owns catalog + view + template + URL; `admin_dashboard` keeps
  only the generic schema renderer. Disable `ai_assistant` → panel + nav vanish.
- No plugin→plugin imports; agent_core's secondary panel keeps rendering via the
  generic path (or its own contribution).

## Testing
- `DATABASE_URL='sqlite:///:memory:'` suite:
  - `get_llm_provider('deepseek')` resolves to DeepSeekProvider (key mocked);
    `'deepseek'` in `_PROVIDER_CLASSES` (mirrors the apikey test).
  - Catalog/connected-filter: a provider with a key is "connected"; without, it
    sits in the picker; Ollama connectable without a key.
  - Connect → appears connected + leaves picker; Disconnect → reverse + active
    reassigned.
  - **3 permission-boundary tests** on the new panel URL (anon / non-staff /
    staff).
  - Disable-guard: panel + nav gone when `ai_assistant` disabled
    (`admin_dashboard/tests/test_disable_guards.py`).
- `makemigrations --check` clean (no model → no migration).

## Out of scope (YAGNI)
- Live key validation / balance display beyond the existing Test button.
- Per-provider model auto-discovery beyond the existing Fetch button.
- Multi-key / multi-account per provider; provider priority ordering UI.
