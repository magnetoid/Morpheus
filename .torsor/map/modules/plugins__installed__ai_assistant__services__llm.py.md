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

# plugins/installed/ai_assistant/services/llm.py

Symbols in `plugins/installed/ai_assistant/services/llm.py`.

- L40 `_truncated_while_reasoning(response)` (function) — True when a completion came back empty because the model hit its token
- L60 `guardrail_refusal()` (function) — Why a model call must not run now, or '' to allow.
- L71 `_guarded(complete)` (function)
- L82 `_paused_guard(embed)` (function) — Embeddings cost little and are not priced, so only the kill switch applies.
- L96 `LLMGateway` (class) — Abstract base — all providers implement this interface.
- L107 `__init_subclass__(cls, **kwargs)` (method)
- L115 `complete(self, prompt: str, system: str='', temperature: float=0.7, max_tokens: int=1000, **kwargs)` (method)
- L125 `embed(self, text: str)` (method)
- L127 `stream(self, prompt: str, system: str='', **kwargs)` (method) — Default: non-streaming fallback.
- L131 `_log(self, interaction_type: str, prompt: str, result: str, prompt_tokens: int, completion_tokens: int, cost_usd: float, latency_ms: int, success: bool=True, error: str='', **context)` (method) — Log every AI call to AIInteraction. Never raises.
- L170 `OpenAIGateway` (class) — OpenAI Chat Completions. Also covers OpenAI-compatible endpoints
- L174 `__init__(self, cfg: ProviderConfig | None=None)` (method)
- L185 `complete(self, prompt: str, system: str='', temperature: float=0.7, max_tokens: int=1000, **kwargs)` (method)
- L259 `embed(self, text: str)` (method)
- L263 `_estimate_cost(self, prompt_tokens: int, completion_tokens: int)` (method)
- L273 `AnthropicGateway` (class)
- L274 `__init__(self, cfg: ProviderConfig | None=None)` (method)
- L292 `complete(self, prompt: str, system: str='', temperature: float=0.7, max_tokens: int=1000, **kwargs)` (method)
- L326 `embed(self, text: str)` (method)
- L337 `GeminiGateway` (class) — Google Gemini via REST. Avoids extra SDK dependency.
- L340 `__init__(self, cfg: ProviderConfig | None=None)` (method)
- L348 `complete(self, prompt: str, system: str='', temperature: float=0.7, max_tokens: int=1000, **kwargs)` (method)
- L396 `embed(self, text: str)` (method)
- L412 `OpenRouterGateway` (class) — OpenRouter is OpenAI-API-compatible — reuse the OpenAI client with
- L416 `__init__(self, cfg: ProviderConfig | None=None)` (method)
- L423 `embed(self, text: str)` (method)
- L432 `GrokGateway` (class) — xAI's Grok exposes an OpenAI-compatible Chat Completions API at
- L436 `__init__(self, cfg: ProviderConfig | None=None)` (method)
- L442 `embed(self, text: str)` (method)
- L453 `ApikeyFunGateway` (class) — apikey.fun — a unified LLM gateway exposing an OpenAI-compatible Chat
- L458 `__init__(self, cfg: ProviderConfig | None=None)` (method)
- L464 `embed(self, text: str)` (method)
- L471 `DeepSeekGateway` (class) — DeepSeek exposes an OpenAI-compatible Chat Completions API at
- L477 `__init__(self, cfg: ProviderConfig | None=None)` (method)
- L485 `embed(self, text: str)` (method)
- L495 `PackyGateway` (class) — Packy (www.packyapi.com) via its Anthropic-compatible Messages API — a
- L502 `__init__(self, cfg: ProviderConfig | None=None)` (method)
- L509 `OllamaGateway` (class) — Local Ollama instance — full privacy, no data leaves the server.
- L512 `__init__(self, cfg: ProviderConfig | None=None)` (method)
- L518 `_headers(self)` (method)
- L524 `complete(self, prompt: str, system: str='', temperature: float=0.7, max_tokens: int=1000, **kwargs)` (method)
- L554 `embed(self, text: str)` (method)
- L578 `get_llm()` (function) — Factory — returns a gateway for the active provider chosen in
