---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:57'
updated: '2026-06-13T00:49:57'
---

# core/agents/llm.py

Symbols in `core/agents/llm.py`.

- L44 `_openai_client(api_key: str='', base_url: str='', **extra)` (function) — Construct an `openai.OpenAI` client with prod-sane defaults.
- L67 `_llm_breaker(fn: Callable)` (function) — Wrap a provider's respond() in LLM_BREAKER so consecutive failures
- L99 `LLMMessage` (class)
- L108 `LLMToolCall` (class) — A tool invocation requested by the model.
- L117 `LLMResponse` (class)
- L126 `is_tool_call(self)` (method)
- L130 `LLMProvider` (class) — A provider knows how to translate `LLMMessage` + tool list into a response.
- L137 `respond(self, *, messages: list[LLMMessage], tools: list[Any] | None=None, temperature: float=0.3, max_tokens: int=1024)` (method)
- L152 `OpenAIProvider` (class)
- L155 `__init__(self, model: str | None=None)` (method)
- L163 `_convert_messages(self, messages: list[LLMMessage])` (method)
- L192 `respond(self, *, messages: list[LLMMessage], tools: list[Any] | None=None, temperature: float=0.3, max_tokens: int=1024)` (method)
- L233 `AnthropicProvider` (class)
- L236 `__init__(self, model: str | None=None)` (method)
- L253 `_convert(self, messages: list[LLMMessage])` (method)
- L294 `respond(self, *, messages: list[LLMMessage], tools: list[Any] | None=None, temperature: float=0.3, max_tokens: int=1024)` (method)
- L345 `OllamaProvider` (class)
- L348 `__init__(self, model: str | None=None)` (method)
- L359 `respond(self, *, messages: list[LLMMessage], tools: list[Any] | None=None, temperature: float=0.3, max_tokens: int=1024)` (method)
- L400 `GeminiProvider` (class)
- L403 `__init__(self, model: str | None=None)` (method)
- L418 `respond(self, *, messages: list[LLMMessage], tools: list[Any] | None=None, temperature: float=0.3, max_tokens: int=1024)` (method)
- L475 `OpenRouterProvider` (class)
- L478 `__init__(self, model: str | None=None)` (method)
- L494 `GrokProvider` (class)
- L497 `__init__(self, model: str | None=None)` (method)
- L513 `PackyProvider` (class)
- L516 `__init__(self, model: str | None=None)` (method)
- L534 `HermesProvider` (class)
- L537 `__init__(self, model: str | None=None)` (method)
- L553 `MockLLMProvider` (class) — Scripted provider for tests.
- L562 `__init__(self, responses: Iterable[LLMResponse] | None=None, *, echo_user: bool=True)` (method)
- L573 `push(self, response: LLMResponse)` (method)
- L576 `respond(self, *, messages: list[LLMMessage], tools: list[Any] | None=None, temperature: float=0.3, max_tokens: int=1024)` (method)
- L612 `get_llm_provider(name: str | None=None, *, model: str | None=None)` (function) — Resolve the active provider. Reads the ai_assistant plugin config (so
- L642 `_UnconfiguredProvider` (class) — Returns a fixed help message every time. Used when the real provider
- L649 `__init__(self, message: str)` (method)
- L653 `respond(self, *, messages: list[LLMMessage], tools: list[Any] | None=None, temperature: float=0.3, max_tokens: int=1024)` (method)
- L664 `_make_unconfigured_mock(message: str)` (function)
