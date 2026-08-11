# Audiobooks plugin — 2026-06

> A separate `audiobooks` plugin (`requires=['book_product']`) that adds an
> **audiobook edition** to a book as a **real priced catalog variant**, plays it
> in a **modal** on the PDP when ready, and (next step) generates the narration
> with **ElevenLabs**. Owner decisions (2026-06): audiobook = real priced variant;
> **scaffold the shape first**, wire ElevenLabs generation as the immediate next step.

## Why a plugin (not in book_product / core)
Audiobooks are a domain, not a book attribute: TTS integration + API keys, audio
storage, a player, generation jobs, settings. Per CLAUDE.md ("when in doubt, it's
a plugin") + ADR 0006. `book_product` stays focused on print/text. Disable
`audiobooks` → the audio, player, settings, and (the audiobook variants stay as
plain variants but) the player/generation vanish. `requires=['book_product']`.

## How it maps onto what already exists (no new commerce primitives)
- **catalog.ProductVariant** already has `variant_type` (`physical|digital|virtual`),
  `price`, `sku`, `requires_shipping`. An audiobook edition is a `variant_type='digital'`
  variant (no shipping). It already shows in the PDP "Choose an edition" picker
  (`themes/.../product_detail.html`) and is purchasable (`orders.services.add(variant_id=…)`).
- So the plugin does NOT build cart/checkout/variant UI — it ATTACHES audio + a
  player + generation to an existing digital variant.

## Model (`audiobooks/models.py`)
`Audiobook` — OneToOne to **catalog.ProductVariant** (the audiobook edition):
- `variant` OneToOneField(ProductVariant, related_name='audiobook')
- `audio_file` FileField (full narration; upload now, ElevenLabs later)
- `sample_file` FileField (free preview clip, blank)
- `narrator` Char, `duration_seconds` PositiveInt(null)
- `source` Char choices `uploaded|elevenlabs` (default uploaded)
- `status` Char `none|generating|ready|failed` (default none; `ready` ⇢ player shows)
- `elevenlabs_voice_id` Char (blank), `created_at`/`updated_at`
- `is_ready` property = `status=='ready' and audio_file`

Migration `0001_initial`. (Audio bytes live on the FileField / media storage.)

## Admin — next to the cover-PDF upload (the user's "everywhere PDF is uploaded")
`book_product` edits `BookProduct.cover_pdf` in the product form via
`book_product/dashboard.save_book_fields`. The audiobooks plugin contributes an
**"Audiobook edition"** subsection into the same book form area:
- "Add audiobook edition" → creates a `ProductVariant(variant_type='digital',
  requires_shipping=False, name='Audiobook')` on the product + an `Audiobook` row.
- Fields: price, SKU, narrator, **audio upload** (+ sample), and a disabled
  **"Generate with ElevenLabs"** button (wired in the next step).
- Contribution mechanism: TBD at build — either a product-form block hook or the
  audiobooks plugin's own dashboard partial included where the book section renders.
  (Investigate how `save_book_fields` is invoked from the product save flow first.)

## Storefront
- The audiobook variant already appears in the **"Choose an edition"** picker (it's a
  real variant) — looks/behaves like a variable, as requested.
- The plugin contributes a **`StorefrontBlock`** on the PDP (`pdp_below_form` or a
  dedicated slot): when the selected/var has `audiobook.is_ready`, render a
  **"Listen" button → modal `<audio>` player** (sample for everyone; full track for
  owners — ownership via the order/digital_products token). No audio yet ⇒ renders
  nothing (self-gating, disable-test clean).

## Settings (`audiobooks` SettingsPanel — the ElevenLabs config)
`elevenlabs_api_key` (secret), `elevenlabs_voice_id` (default voice),
`elevenlabs_model` (e.g. `eleven_multilingual_v2`), `auto_generate` (bool, off).
Secret key auto-redacted by the settings surface.

## Generation (NEXT step — scaffolded now, not wired)
`audiobooks/services.py:generate(audiobook)` — chunk the book text
(`BookProduct.synopsis` / Product.description / chapters) → ElevenLabs TTS → stitch
→ store on `audio_file` via the `media` plugin → set `status='ready'`. Runs in a
Celery task; the "Generate" button enqueues it. Bounded + audited. This build ships
the function as a stub raising "not enabled yet" so the shape is testable.

## Delivery (token-gated)
Reuse `digital_products` for the full track: on purchase of the audiobook variant,
grant a download/stream token; the modal streams the full file to owners, sample to
everyone else. (Compose, don't duplicate.)

## Phases
1. **Scaffold** — plugin (apps/plugin/models/migrations/tests) + register in
   `MORPHEUS_DEFAULT_APPS`. `Audiobook` model + migration.
2. **Admin** — "Audiobook edition" subsection in the book product form (create the
   digital variant + upload audio + fields). ElevenLabs **SettingsPanel**.
3. **Storefront** — PDP modal player block (sample/full), self-gating on `is_ready`.
4. **(Next) Generation** — ElevenLabs TTS service + Celery task + Generate button.

## Success criteria
- Disable `audiobooks` → player + settings gone; the variant remains a plain digital
  variant; books intact (disable test).
- An audiobook variant with an uploaded file shows a working modal player on the PDP.
- ElevenLabs key lives only in the audiobooks settings panel (redacted).
- No new cart/checkout code — the audiobook is a real, purchasable digital variant.

## 2026-06-22 — narrate the book PDF + "audiobook on demand"
Generation now sources the **actual book** instead of the marketing blurb:
- `Audiobook.source_pdf` (migration `0002`) holds the narration-source PDF —
  uploadable on the product-form card, kept **separate** from the delivered audio
  so buyers still receive the MP3, not the PDF.
- `pdf_text.extract_pdf_text()` (pypdf, fail-soft → `''` on encrypted/scanned/corrupt)
  pulls the text; `services.source_text()` prefers `source_pdf` → `Product.digital_file`
  → the title/synopsis/description blurb.
- `manage.py backfill_book_formats [--dry-run] [--limit N]` turns every book with a
  `Product.digital_file` PDF into an *audiobook-on-demand* product: an **"E-book"**
  digital variant carrying the PDF **+** the **Audiobook** edition with `source_pdf`
  set. Idempotent; reuses the stored file (no duplication); generates no audio —
  that stays on-demand via the Generate button. New dep: `pypdf`.
