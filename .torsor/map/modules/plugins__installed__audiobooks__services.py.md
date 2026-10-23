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

# plugins/installed/audiobooks/services.py

Symbols in `plugins/installed/audiobooks/services.py`.

- L21 `_config()` (function)
- L34 `_strip_html(text: str)` (function)
- L38 `source_text(audiobook)` (function) — The narration script.
- L66 `get_or_create_audiobook_edition(product, *, sku: str)` (function) — Return the product's Audiobook edition, creating its digital
- L85 `_chunks(text: str, size: int=_MAX_CHARS)` (function) — Split into <=size pieces at sentence boundaries.
- L98 `_tts(text: str, *, api_key: str, voice_id: str, model: str, timeout: int=60)` (function)
- L119 `generate(audiobook)` (function) — Generate narration via ElevenLabs. Never raises — returns a result dict and
