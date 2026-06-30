# Full localization & translation — whole-site multi-language

**Status:** spec, pre-implementation · **Date:** 2026-06-30 · **Owner:** localization plugin + core.i18n

Make the entire Morpheus site translatable to several languages: **UI strings,
catalog content, CMS/blog, and the dashboard**, populated by **AI
auto-translate (editable)**, with visitors landing on **URL-prefixed**
languages (`/en/`, `/fr/`).

## Decisions (locked, per owner)
- **Translate everything**: interface strings + catalog content + CMS/blog +
  admin dashboard.
- **AI auto-translate + editable**: use the existing provider layer to generate
  translations the merchant can edit/approve.
- **URL-prefix routing** (`/en/…`, `/fr/…`) with per-language `hreflang`.
- **Design-first, phased**: ship in safe increments; never break the live
  storefront in one big deploy.

## What already exists (build on it — don't reinvent)
- **Translation overlay model** — generic FK `(content_type, object_id, field,
  language_code)` with `is_machine_translated` ([core/i18n/models.py](../../core/i18n/models.py));
  service layer `translated()/set_translation()/list_enabled_languages()`
  ([core/i18n/services.py](../../core/i18n/services.py)); `{{ obj|trans:"field" }}`
  filter with fallback ([core/i18n/templatetags/morph_i18n.py](../../core/i18n/templatetags/morph_i18n.py)).
- **localization plugin** — Languages picker (persists ISO codes to
  `StoreSettings`) + read-only translations index
  ([plugins/installed/localization/views.py](../../plugins/installed/localization/views.py)).
- **Agent tools** — `i18n.translate_product`, `i18n.list_translations`.
- `USE_I18N=True`; ~86 `{% trans %}` tags in some plugin templates.
- Market-driven `Content-Language` header (markets middleware).

## Gaps → target
- **No URL routing / language activation** → add `LocaleMiddleware` +
  `i18n_patterns`, `LANGUAGES` from enabled languages, a language switcher.
- **No gettext workflow** → `LOCALE_PATHS`, makemessages/compilemessages, expand
  `{% trans %}` coverage to core/theme/checkout/account/email templates.
- **Content editor read-only; emails/categories/CMS untranslated** → inline
  translation editor + AI autofill over the Translation overlay, extended to all
  content types + `EmailTemplate`.
- **hreflang per-market only** → per-language alternates.

## Phased plan (each phase ships + verifies independently)

### Phase 1 — Routing foundation (prereq for everything)
- `LANGUAGES` derived from `list_enabled_languages()` (default `en`); add
  `django.middleware.locale.LocaleMiddleware` (after Session, before Common);
  wrap storefront URLs in `i18n_patterns(prefix_default_language=False)` so the
  default language stays unprefixed (no SEO regression) and others get `/fr/…`.
- **Language switcher** `StorefrontBlock` (writes the language cookie + redirects
  to the prefixed URL); persist choice on the customer when logged in.
- Per-language `hreflang` alternates (extend seo templatetag).
- Verify: `/fr/` resolves, switcher round-trips, default URLs unchanged, hreflang
  emits one tag per enabled language. **Highest risk (URL/middleware) — ships
  alone.**

### Phase 2 — UI strings (gettext)
- `LOCALE_PATHS=[BASE_DIR/'locale']`; `manage.py morph_translate_ui` wrapper
  around makemessages/compilemessages; audit + add `{% trans %}`/`{% blocktrans %}`
  to core/theme/checkout/cart/account templates.
- **AI autofill of `.po`** — a command that fills empty msgstr via the provider,
  flagged fuzzy for review.
- Verify: switching language localizes chrome; `.po` round-trips; CI compiles `.mo`.

### Phase 3 — Content translation (catalog + CMS) editor + AI autofill
- Inline **translation editor** in the localization dashboard: per object, per
  enabled language, edit the Translation overlay for name/description/etc.;
  per-field **"AI translate"** + bulk **"Auto-translate all"** (Celery task,
  `is_machine_translated=True`, never overwrites human-edited rows).
- Extend coverage: categories, collections, CMS pages/blog, metafields. Retire
  the dead `Product.localized_translations` JSONField.
- Storefront templates read via `|trans` so translated content shows per locale.
- Verify: a product shows translated name on `/fr/`; autofill populates; human
  edits win over machine.

### Phase 4 — Emails, dashboard UI, formatting, RTL
- Per-language `EmailTemplate` (subject/body) via the overlay; transactional
  emails render in the recipient's language.
- Translate the **admin dashboard** strings (gettext) + a dashboard language pref.
- Locale-aware number/date formatting (`USE_L10N`, per-locale formats);
  multi-currency already exists.
- **RTL** stylesheet + `dir` switching for ar/he.
- Verify: order email in customer language; dashboard in chosen language; RTL renders.

## Ownership / boundaries
- `localization` plugin owns the dashboard editor, languages, switcher block,
  autofill tasks, and AI-translate buttons. `core.i18n` owns the overlay model +
  services + the `LANGUAGES`/middleware wiring (i18n kernel is core). No
  plugin→plugin imports; storefront integration via `StorefrontBlock`.
- AI translation goes through the existing provider layer (`get_llm_provider`),
  honoring the active provider; degrades to "no provider configured."

## Testing (per phase)
- Phase 1: URL resolution for `/`, `/fr/`; switcher redirect; hreflang count;
  default-language URLs unchanged (snapshot key routes).
- Phase 2: a trans string localizes; makemessages finds new strings; `.mo` compiles in CI.
- Phase 3: overlay editor saves; AI autofill marks machine + skips human rows;
  storefront renders translated field; **3 permission-boundary tests** on the editor.
- Phase 4: localized email + dashboard + format; RTL attribute present.
- `makemigrations --check` clean (overlay model already exists; emails reuse it).

## Out of scope (v1)
- Translation memory / TMX; third-party TMS (Crowdin/Lokalise) sync; per-word
  billing; auto-language-detect by geo-IP (use Accept-Language + switcher);
  translated slugs/URLs beyond the language prefix.
