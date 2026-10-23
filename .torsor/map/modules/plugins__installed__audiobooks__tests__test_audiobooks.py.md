---
type: map
status: derived
tags:
- map
links: []
created: '2026-10-23T04:51:50'
updated: '2026-10-23T04:51:50'
rules: []
---

# plugins/installed/audiobooks/tests/test_audiobooks.py

Symbols in `plugins/installed/audiobooks/tests/test_audiobooks.py`.

- L18 `AudiobookModelTests` (class)
- L19 `_audiobook_variant(self)` (method)
- L38 `test_is_ready_requires_both_status_and_file(self)` (method)
- L47 `test_onetoone_to_variant(self)` (method)
- L56 `ProductFormHandlerTests` (class) — The PRODUCT_FORM_SAVED handler creates the audiobook EDITION as a real
- L60 `_book(self)` (method)
- L74 `test_saved_handler_creates_audiobook_variant(self)` (method)
- L96 `test_audiobook_variant_is_digital_behaving_at_checkout(self)` (method) — The new 'audiobook' type must behave like 'digital' where it matters:
- L110 `test_non_book_product_is_ignored(self)` (method)
- L130 `StorefrontPlayerTests` (class) — The PDP player self-gates: `audiobook_for` returns an audiobook only when
- L134 `test_audiobook_for_returns_ready_only(self)` (method)
- L161 `test_audiobook_for_accepts_graphql_dict_product(self)` (method) — The storefront PDP passes `product` as a GraphQL dict, not the model.
- L191 `GenerationTests` (class) — ElevenLabs generation (HTTP mocked — no real API key needed).
- L194 `_audiobook(self)` (method)
- L221 `test_generate_success_sets_ready(self, _tts, _cfg)` (method)
- L237 `test_generate_without_key_fails(self, _cfg)` (method)
- L248 `PdfNarrationSourceTests` (class) — source_text() narrates the book PDF when present, else the blurb.
- L251 `_audiobook(self, *, synopsis='')` (method)
- L273 `_pdf_bytes(self, text)` (method)
- L285 `test_source_text_prefers_pdf_over_blurb(self)` (method)
- L298 `test_source_text_falls_back_to_blurb_without_pdf(self)` (method)
