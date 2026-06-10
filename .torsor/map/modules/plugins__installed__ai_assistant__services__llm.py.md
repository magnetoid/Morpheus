---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-09T21:57:01'
updated: '2026-06-09T21:57:01'
---

# plugins/installed/ai_assistant/services/llm.py

Symbols in `plugins/installed/ai_assistant/services/llm.py`.

- L27 `LLMGateway` (class) — Abstract base — all providers implement this interface.
- L33 `complete(self, prompt: str, system: str='', temperature: float=0.7, max_tokens: int=1000, **kwargs)` (method)
- L37 `embed(self, text: str)` (method)
- L39 `stream(self, prompt: str, system: str='', **kwargs)` (method) — Default: non-streaming fallback.
- L43 `_log(self, interaction_type: str, prompt: str, result: str, prompt_tokens: int, completion_tokens: int, cost_usd: float, latency_ms: int, success: bool=True, error: str='', **context)` (method) — Log every AI call to AIInteraction. Never raises.
- L68 `OpenAIGateway` (class) — OpenAI Chat Completions. Also covers OpenAI-compatible endpoints
- L72 `__init__(self, cfg: ProviderConfig | None=None)` (method)
- L82 `complete(self, prompt: str, system: str='', temperature: float=0.7, max_tokens: int=1000, **kwargs)` (method)
- L115 `embed(self, text: str)` (method)
- L119 `_estimate_cost(self, prompt_tokens: int, completion_tokens: int)` (method)
- L129 `AnthropicGateway` (class)
- L130 `__init__(self, cfg: ProviderConfig | None=None)` (method)
- L136 `complete(self, prompt: str, system: str='', temperature: float=0.7, max_tokens: int=1000, **kwargs)` (method)
- L157 `embed(self, text: str)` (method)
- L168 `GeminiGateway` (class) — Google Gemini via REST. Avoids extra SDK dependency.
- L171 `__init__(self, cfg: ProviderConfig | None=None)` (method)
- L177 `complete(self, prompt: str, system: str='', temperature: float=0.7, max_tokens: int=1000, **kwargs)` (method)
- L216 `embed(self, text: str)` (method)
- L228 `OpenRouterGateway` (class) — OpenRouter is OpenAI-API-compatible — reuse the OpenAI client with
- L232 `__init__(self, cfg: ProviderConfig | None=None)` (method)
- L239 `embed(self, text: str)` (method)
- L248 `GrokGateway` (class) — xAI's Grok exposes an OpenAI-compatible Chat Completions API at
- L252 `__init__(self, cfg: ProviderConfig | None=None)` (method)
- L258 `embed(self, text: str)` (method)
- L269 `PackyGateway` (class) — Packy (www.packyapi.com) — Chinese LLM gateway that proxies Claude /
- L275 `__init__(self, cfg: ProviderConfig | None=None)` (method)
- L281 `embed(self, text: str)` (method)
- L290 `OllamaGateway` (class) — Local Ollama instance — full privacy, no data leaves the server.
- L293 `__init__(self, cfg: ProviderConfig | None=None)` (method)
- L299 `_headers(self)` (method)
- L305 `complete(self, prompt: str, system: str='', temperature: float=0.7, max_tokens: int=1000, **kwargs)` (method)
- L329 `embed(self, text: str)` (method)
- L351 `get_llm()` (function) — Factory — returns a gateway for the active provider chosen in
