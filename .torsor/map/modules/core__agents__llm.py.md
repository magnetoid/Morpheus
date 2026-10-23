---
type: map
status: derived
tags:
- map
links: []
created: '2026-10-23T04:51:49'
updated: '2026-10-23T04:51:49'
rules: []
---

# core/agents/llm.py

Symbols in `core/agents/llm.py`.

- L64 `is_degraded_response(text: str | None)` (function) — True when `text` is an outage sentinel rather than model output.
- L69 `_openai_client(api_key: str='', base_url: str='', **extra)` (function) — Construct an `openai.OpenAI` client with prod-sane defaults.
- L92 `_llm_breaker(fn: Callable)` (function) — Wrap a provider's respond() in a per-provider Circuit Breaker so consecutive failures
- L167 `LLMMessage` (class)
- L176 `LLMToolCall` (class) — A tool invocation requested by the model.
- L189 `LLMResponse` (class)
- L198 `is_tool_call(self)` (method)
- L202 `LLMProvider` (class) — A provider knows how to translate `LLMMessage` + tool list into a response.
- L208 `__init_subclass__(cls, **kwargs)` (method)
- L219 `respond(self, *, messages: list[LLMMessage], tools: list[Any] | None=None, temperature: float=0.3, max_tokens: int=1024)` (method)
- L242 `_truncated_while_reasoning(completion: Any)` (function) — True when a completion came back empty because the model hit its token
- L255 `OpenAIProvider` (class)
- L261 `__init__(self, model: str | None=None)` (method)
- L269 `_convert_messages(self, messages: list[LLMMessage])` (method)
- L298 `respond(self, *, messages: list[LLMMessage], tools: list[Any] | None=None, temperature: float=0.3, max_tokens: int=1024)` (method)
- L362 `AnthropicProvider` (class)
- L365 `__init__(self, model: str | None=None)` (method)
- L382 `_convert(self, messages: list[LLMMessage])` (method)
- L423 `respond(self, *, messages: list[LLMMessage], tools: list[Any] | None=None, temperature: float=0.3, max_tokens: int=1024)` (method)
- L474 `OllamaProvider` (class)
- L477 `__init__(self, model: str | None=None)` (method)
- L488 `respond(self, *, messages: list[LLMMessage], tools: list[Any] | None=None, temperature: float=0.3, max_tokens: int=1024)` (method)
- L529 `GeminiProvider` (class)
- L532 `__init__(self, model: str | None=None)` (method)
- L547 `respond(self, *, messages: list[LLMMessage], tools: list[Any] | None=None, temperature: float=0.3, max_tokens: int=1024)` (method)
- L604 `OpenRouterProvider` (class)
- L607 `__init__(self, model: str | None=None)` (method)
- L623 `GrokProvider` (class)
- L626 `__init__(self, model: str | None=None)` (method)
- L642 `PackyProvider` (class)
- L645 `__init__(self, model: str | None=None)` (method)
- L663 `HermesProvider` (class)
- L666 `__init__(self, model: str | None=None)` (method)
- L682 `ApikeyProvider` (class)
- L685 `__init__(self, model: str | None=None)` (method)
- L701 `DeepSeekProvider` (class)
- L704 `__init__(self, model: str | None=None)` (method)
- L723 `MoonshotProvider` (class)
- L726 `__init__(self, model: str | None=None)` (method)
- L745 `QwenProvider` (class)
- L749 `__init__(self, model: str | None=None)` (method)
- L765 `MockLLMProvider` (class) — Scripted provider for tests.
- L774 `__init__(self, responses: Iterable[LLMResponse] | None=None, *, echo_user: bool=True)` (method)
- L785 `push(self, response: LLMResponse)` (method)
- L788 `respond(self, *, messages: list[LLMMessage], tools: list[Any] | None=None, temperature: float=0.3, max_tokens: int=1024)` (method)
- L828 `FallbackProviderRouter` (class) — Automated Fallback Router to ensure 99.9% uptime.
- L837 `__init__(self, primary: LLMProvider, secondaries: list[LLMProvider])` (method)
- L842 `respond(self, *, messages: list[LLMMessage], tools: list[Any] | None=None, temperature: float=0.3, max_tokens: int=1024)` (method)
- L900 `get_llm_provider(name: str | None=None, *, model: str | None=None, use_fallback: bool=True)` (function) — Resolve the active provider. Reads the ai_assistant plugin config (so
- L964 `_UnconfiguredProvider` (class) — Returns a fixed help message every time. Used when the real provider
- L971 `__init__(self, message: str)` (method)
- L975 `respond(self, *, messages: list[LLMMessage], tools: list[Any] | None=None, temperature: float=0.3, max_tokens: int=1024)` (method)
- L986 `_make_unconfigured_mock(message: str)` (function)
