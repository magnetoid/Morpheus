---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-02T18:07:51'
updated: '2026-06-02T18:07:51'
---

# core/agents/llm.py

Symbols in `core/agents/llm.py`.

- L39 `_openai_client(api_key: str='', base_url: str='', **extra)` (function) — Construct an `openai.OpenAI` client with prod-sane defaults.
- L61 `_llm_breaker(fn: Callable)` (function) — Wrap a provider's respond() in LLM_BREAKER so consecutive failures
- L89 `LLMMessage` (class)
- L98 `LLMToolCall` (class) — A tool invocation requested by the model.
- L106 `LLMResponse` (class)
- L115 `is_tool_call(self)` (method)
- L119 `LLMProvider` (class) — A provider knows how to translate `LLMMessage` + tool list into a response.
- L126 `respond(self, *, messages: list[LLMMessage], tools: list[Any] | None=None, temperature: float=0.3, max_tokens: int=1024)` (method)
- L142 `OpenAIProvider` (class)
- L145 `__init__(self, model: str | None=None)` (method)
- L152 `_convert_messages(self, messages: list[LLMMessage])` (method)
- L179 `respond(self, *, messages: list[LLMMessage], tools: list[Any] | None=None, temperature: float=0.3, max_tokens: int=1024)` (method)
- L220 `AnthropicProvider` (class)
- L223 `__init__(self, model: str | None=None)` (method)
- L239 `_convert(self, messages: list[LLMMessage])` (method)
- L274 `respond(self, *, messages: list[LLMMessage], tools: list[Any] | None=None, temperature: float=0.3, max_tokens: int=1024)` (method)
- L323 `OllamaProvider` (class)
- L326 `__init__(self, model: str | None=None)` (method)
- L336 `respond(self, *, messages: list[LLMMessage], tools: list[Any] | None=None, temperature: float=0.3, max_tokens: int=1024)` (method)
- L377 `GeminiProvider` (class)
- L380 `__init__(self, model: str | None=None)` (method)
- L392 `respond(self, *, messages: list[LLMMessage], tools: list[Any] | None=None, temperature: float=0.3, max_tokens: int=1024)` (method)
- L449 `OpenRouterProvider` (class)
- L452 `__init__(self, model: str | None=None)` (method)
- L467 `GrokProvider` (class)
- L470 `__init__(self, model: str | None=None)` (method)
- L485 `PackyProvider` (class)
- L488 `__init__(self, model: str | None=None)` (method)
- L503 `MockLLMProvider` (class) — Scripted provider for tests.
- L512 `__init__(self, responses: Iterable[LLMResponse] | None=None, *, echo_user: bool=True)` (method)
- L523 `push(self, response: LLMResponse)` (method)
- L526 `respond(self, *, messages: list[LLMMessage], tools: list[Any] | None=None, temperature: float=0.3, max_tokens: int=1024)` (method)
- L561 `get_llm_provider(name: str | None=None, *, model: str | None=None)` (function) — Resolve the active provider. Reads the ai_assistant plugin config (so
- L590 `_UnconfiguredProvider` (class) — Returns a fixed help message every time. Used when the real provider
- L597 `__init__(self, message: str)` (method)
- L601 `respond(self, *, messages: list[LLMMessage], tools: list[Any] | None=None, temperature: float=0.3, max_tokens: int=1024)` (method)
- L612 `_make_unconfigured_mock(message: str)` (function)
