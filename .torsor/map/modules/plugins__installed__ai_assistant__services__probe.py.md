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

# plugins/installed/ai_assistant/services/probe.py

Symbols in `plugins/installed/ai_assistant/services/probe.py`.

- L33 `_http_get(url: str, headers: dict[str, str])` (function)
- L57 `_ok(models: list[dict])` (function)
- L61 `_fail(error: str)` (function)
- L68 `probe_openai(*, api_key: str, base_url: str='')` (function)
- L84 `probe_anthropic(*, api_key: str, base_url: str='')` (function)
- L110 `probe_gemini(*, api_key: str, base_url: str='')` (function)
- L136 `probe_openrouter(*, api_key: str, base_url: str='')` (function)
- L159 `probe_grok(*, api_key: str, base_url: str='')` (function)
- L178 `probe_packy(*, api_key: str, base_url: str='')` (function)
- L197 `probe_ollama(*, api_key: str='', base_url: str='')` (function)
- L217 `_probe_openai_compatible(*, api_key: str, base_url: str, default_base: str, label: str)` (function)
- L230 `probe_deepseek(*, api_key: str, base_url: str='')` (function)
- L239 `probe_apikey(*, api_key: str, base_url: str='')` (function)
- L248 `probe_hermes(*, api_key: str, base_url: str='')` (function)
- L257 `probe_moonshot(*, api_key: str, base_url: str='')` (function)
- L266 `probe_qwen(*, api_key: str, base_url: str='')` (function)
- L291 `probe(provider: str, *, api_key: str='', base_url: str='')` (function)
