---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:57'
updated: '2026-06-13T00:49:57'
---

# plugins/installed/audiobooks/services.py

Symbols in `plugins/installed/audiobooks/services.py`.

- L21 `_config()` (function)
- L34 `_strip_html(text: str)` (function)
- L38 `source_text(audiobook)` (function) — The narration script: title + author + synopsis + long description.
- L53 `_chunks(text: str, size: int=_MAX_CHARS)` (function) — Split into <=size pieces at sentence boundaries.
- L66 `_tts(text: str, *, api_key: str, voice_id: str, model: str, timeout: int=60)` (function)
- L83 `generate(audiobook)` (function) — Generate narration via ElevenLabs. Never raises — returns a result dict and
