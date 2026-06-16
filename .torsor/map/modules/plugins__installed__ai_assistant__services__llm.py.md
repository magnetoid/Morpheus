---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:57'
updated: '2026-06-13T00:49:57'
---

# plugins/installed/ai_assistant/services/llm.py

Symbols in `plugins/installed/ai_assistant/services/llm.py`.

- L27 `LLMGateway` (class) — Abstract base — all providers implement this interface.
- L33 `complete(self, prompt: str, system: str='', temperature: float=0.7, max_tokens: int=1000, **kwargs)` (method)
- L43 `embed(self, text: str)` (method)
- L45 `stream(self, prompt: str, system: str='', **kwargs)` (method) — Default: non-streaming fallback.
- L49 `_log(self, interaction_type: str, prompt: str, result: str, prompt_tokens: int, completion_tokens: int, cost_usd: float, latency_ms: int, success: bool=True, error: str='', **context)` (method) — Log every AI call to AIInteraction. Never raises.
- L88 `OpenAIGateway` (class) — OpenAI Chat Completions. Also covers OpenAI-compatible endpoints
- L92 `__init__(self, cfg: ProviderConfig | None=None)` (method)
- L103 `complete(self, prompt: str, system: str='', temperature: float=0.7, max_tokens: int=1000, **kwargs)` (method)
- L147 `embed(self, text: str)` (method)
- L151 `_estimate_cost(self, prompt_tokens: int, completion_tokens: int)` (method)
- L161 `AnthropicGateway` (class)
- L162 `__init__(self, cfg: ProviderConfig | None=None)` (method)
- L171 `complete(self, prompt: str, system: str='', temperature: float=0.7, max_tokens: int=1000, **kwargs)` (method)
- L205 `embed(self, text: str)` (method)
- L216 `GeminiGateway` (class) — Google Gemini via REST. Avoids extra SDK dependency.
- L219 `__init__(self, cfg: ProviderConfig | None=None)` (method)
- L227 `complete(self, prompt: str, system: str='', temperature: float=0.7, max_tokens: int=1000, **kwargs)` (method)
- L275 `embed(self, text: str)` (method)
- L291 `OpenRouterGateway` (class) — OpenRouter is OpenAI-API-compatible — reuse the OpenAI client with
- L295 `__init__(self, cfg: ProviderConfig | None=None)` (method)
- L302 `embed(self, text: str)` (method)
- L311 `GrokGateway` (class) — xAI's Grok exposes an OpenAI-compatible Chat Completions API at
- L315 `__init__(self, cfg: ProviderConfig | None=None)` (method)
- L321 `embed(self, text: str)` (method)
- L332 `PackyGateway` (class) — Packy (www.packyapi.com) — Chinese LLM gateway that proxies Claude /
- L338 `__init__(self, cfg: ProviderConfig | None=None)` (method)
- L344 `embed(self, text: str)` (method)
- L353 `OllamaGateway` (class) — Local Ollama instance — full privacy, no data leaves the server.
- L356 `__init__(self, cfg: ProviderConfig | None=None)` (method)
- L362 `_headers(self)` (method)
- L368 `complete(self, prompt: str, system: str='', temperature: float=0.7, max_tokens: int=1000, **kwargs)` (method)
- L398 `embed(self, text: str)` (method)
- L420 `get_llm()` (function) — Factory — returns a gateway for the active provider chosen in
