"""
LLM provider abstraction.

The runtime is provider-agnostic. Each concrete provider implements a
single method — `respond(messages, tools, ...)` — that returns either
"final text" or "I want to call these tools." The runtime drives the
loop; providers just translate.

Built-in providers:
* `OpenAIProvider` — function-calling via the official SDK.
* `AnthropicProvider` — tool-use via the official SDK.
* `OllamaProvider` — local inference (best-effort tool support).
* `MockLLMProvider` — deterministic, used in tests.
"""

# Lazy (in-function) SDK + provider-config imports keep this load-order-safe.
# Pre-existing typing/import idioms across the provider classes.
# ruff: noqa: PLC0415, UP035, UP037, I001, F541

from __future__ import annotations

import functools
import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable

from django.conf import settings

from core.circuit_breaker import CircuitOpenError, get_llm_breaker
from django.core.cache import cache

logger = logging.getLogger('morpheus.agents.llm')


# How long a single LLM provider call may take before we abort.
# Must be LESS than `--timeout` in scripts/docker-entrypoint.sh
# (currently 30s) so the gateway times out cleanly and the worker is
# released — gunicorn killing the worker mid-flight is much worse than
# the LLM call failing with a recoverable error.
LLM_HTTP_TIMEOUT_SECS = 20


def _openai_client(api_key: str = '', base_url: str = '', **extra):
    """Construct an `openai.OpenAI` client with prod-sane defaults.

    The OpenAI SDK retries twice on failures by default (so one Packy
    503 turns into three calls and ~24s of held-worker time). We
    disable that — the circuit breaker and the gunicorn timeout are
    the right layers to handle persistent upstream failure, not the
    SDK retry loop.
    """
    import openai

    kwargs: dict[str, Any] = {
        'timeout': LLM_HTTP_TIMEOUT_SECS,
        'max_retries': 0,
    }
    if api_key:
        kwargs['api_key'] = api_key
    if base_url:
        kwargs['base_url'] = base_url
    kwargs.update(extra)
    return openai.OpenAI(**kwargs)


def _llm_breaker(fn: Callable) -> Callable:
    """Wrap a provider's respond() in a per-provider Circuit Breaker so consecutive failures
    trip the circuit and follow-up calls fail fast instead of stacking
    30s timeouts. CircuitOpenError → clean LLMResponse the runtime can
    surface to the user/agent without crashing the request.
    """

    @functools.wraps(fn)
    def wrapped(self, *args, **kwargs):
        # Generate cache key based on messages and tools
        messages = kwargs.get('messages', [])
        tools = kwargs.get('tools', [])

        # Only cache queries without tools to avoid caching side-effects,
        # or cache specific repeatable queries.
        # For this high-performance spec, we will implement a semantic cache layer
        # by hashing the messages.
        cache_key = None
        if not tools:
            try:
                import hashlib

                msg_str = json.dumps(
                    [{'role': m.role, 'content': m.content} for m in messages], sort_keys=True
                )
                cache_key = f'llm_cache_{self.name}_{self.model}_{hashlib.sha256(msg_str.encode()).hexdigest()}'
                cached_resp = cache.get(cache_key)
                if cached_resp:
                    logger.debug('llm provider %s returning cached response', self.name)
                    # Convert dict back to LLMResponse
                    return LLMResponse(**cached_resp)
            except Exception:  # noqa: S110 — best-effort cache read; fall through to live call
                pass

        breaker = get_llm_breaker(self.name)
        try:
            with breaker:
                resp = fn(self, *args, **kwargs)
                if cache_key and not resp.is_tool_call:
                    try:
                        cache_dict = {
                            'text': resp.text,
                            'prompt_tokens': resp.prompt_tokens,
                            'completion_tokens': resp.completion_tokens,
                            'model': resp.model,
                        }
                        cache.set(cache_key, cache_dict, timeout=3600)  # Cache for 1 hour
                    except Exception:  # noqa: S110 — best-effort cache write; never block the response
                        pass
                return resp
        except CircuitOpenError as exc:
            logger.warning(
                'llm provider %s short-circuited: %s',
                self.name,
                exc,
            )
            return LLMResponse(
                text=f'[Upstream AI provider is degraded — circuit open. {exc}]',
                model=getattr(self, 'model', '') or 'unknown',
            )

    return wrapped


@dataclass(slots=True)
class LLMMessage:
    role: str  # 'system' | 'user' | 'assistant' | 'tool'
    content: str = ''
    name: str | None = None
    tool_call_id: str | None = None
    tool_calls: list['LLMToolCall'] = field(default_factory=list)


@dataclass(slots=True)
class LLMToolCall:
    """A tool invocation requested by the model."""

    id: str
    name: str
    arguments: dict[str, Any]
    # Set when the provider could not parse the model's raw arguments (e.g.
    # malformed JSON). The runtime surfaces this back to the model as a tool
    # error so it can retry, instead of silently invoking the tool with {}.
    parse_error: str = ''


@dataclass(slots=True)
class LLMResponse:
    text: str = ''
    tool_calls: list[LLMToolCall] = field(default_factory=list)
    prompt_tokens: int = 0
    completion_tokens: int = 0
    model: str = ''
    raw: Any = None

    @property
    def is_tool_call(self) -> bool:
        return bool(self.tool_calls)


class LLMProvider(ABC):
    """A provider knows how to translate `LLMMessage` + tool list into a response."""

    name: str = 'base'
    model: str = ''

    @abstractmethod
    def respond(
        self,
        *,
        messages: list[LLMMessage],
        tools: list[Any] | None = None,
        temperature: float = 0.3,
        max_tokens: int = 1024,
    ) -> LLMResponse: ...


# ─────────────────────────────────────────────────────────────────────────────
# OpenAI
# ─────────────────────────────────────────────────────────────────────────────


class OpenAIProvider(LLMProvider):
    name = 'openai'

    def __init__(self, model: str | None = None) -> None:
        from core.agents.provider_registry import get_provider_config

        cfg = get_provider_config('openai')
        base = cfg.base_url if cfg.base_url and cfg.base_url != 'https://api.openai.com/v1' else ''
        self._client = _openai_client(api_key=cfg.api_key, base_url=base)
        self.model = model or cfg.model or 'gpt-4o-mini'

    def _convert_messages(self, messages: list[LLMMessage]) -> list[dict[str, Any]]:  # type: ignore[override]
        out: list[dict[str, Any]] = []
        for m in messages:
            if m.role == 'tool':
                out.append(
                    {
                        'role': 'tool',
                        'tool_call_id': m.tool_call_id or '',
                        'content': m.content,
                    }
                )
                continue
            entry: dict[str, Any] = {'role': m.role, 'content': m.content}
            if m.tool_calls:
                entry['tool_calls'] = [
                    {
                        'id': tc.id,
                        'type': 'function',
                        'function': {
                            'name': tc.name,
                            'arguments': json.dumps(tc.arguments),
                        },
                    }
                    for tc in m.tool_calls
                ]
            out.append(entry)
        return out

    @_llm_breaker
    def respond(
        self,
        *,
        messages: list[LLMMessage],
        tools: list[Any] | None = None,
        temperature: float = 0.3,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        kwargs: dict[str, Any] = {
            'model': self.model,
            'messages': self._convert_messages(messages),
            'temperature': temperature,
            'max_tokens': max_tokens,
        }
        if tools:
            kwargs['tools'] = [t.to_openai_schema() for t in tools]
        completion = self._client.chat.completions.create(**kwargs)
        choice = completion.choices[0]
        msg = choice.message
        tool_calls: list[LLMToolCall] = []
        for tc in getattr(msg, 'tool_calls', None) or []:
            parse_error = ''
            try:
                args = json.loads(tc.function.arguments or '{}')
            except json.JSONDecodeError as e:
                args = {}
                parse_error = f'malformed JSON arguments: {e}'
                logger.warning('llm: tool %s sent unparseable arguments: %s', tc.function.name, e)
            tool_calls.append(
                LLMToolCall(
                    id=tc.id, name=tc.function.name, arguments=args, parse_error=parse_error
                )
            )
        return LLMResponse(
            text=msg.content or '',
            tool_calls=tool_calls,
            prompt_tokens=getattr(completion.usage, 'prompt_tokens', 0) or 0,
            completion_tokens=getattr(completion.usage, 'completion_tokens', 0) or 0,
            model=self.model,
            raw=completion,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Anthropic
# ─────────────────────────────────────────────────────────────────────────────


class AnthropicProvider(LLMProvider):
    name = 'anthropic'

    def __init__(self, model: str | None = None) -> None:
        import anthropic
        from core.agents.provider_registry import get_provider_config

        cfg = get_provider_config('anthropic')
        # Same timeout discipline as the OpenAI client — must be less
        # than the gunicorn worker timeout so the LLM call fails
        # cleanly instead of getting SIGKILLed.
        anth_kwargs: dict[str, Any] = {
            'timeout': LLM_HTTP_TIMEOUT_SECS,
            'max_retries': 0,
        }
        if cfg.api_key:
            anth_kwargs['api_key'] = cfg.api_key
        self._client = anthropic.Anthropic(**anth_kwargs)
        self.model = model or cfg.model or 'claude-3-5-sonnet-latest'

    def _convert(self, messages: list[LLMMessage]) -> tuple[str, list[dict[str, Any]]]:
        system_chunks: list[str] = []
        out: list[dict[str, Any]] = []
        for m in messages:
            if m.role == 'system':
                if m.content:
                    system_chunks.append(m.content)
                continue
            if m.role == 'tool':
                out.append(
                    {
                        'role': 'user',
                        'content': [
                            {
                                'type': 'tool_result',
                                'tool_use_id': m.tool_call_id or '',
                                'content': m.content,
                            }
                        ],
                    }
                )
                continue
            if m.role == 'assistant' and m.tool_calls:
                blocks: list[dict[str, Any]] = []
                if m.content:
                    blocks.append({'type': 'text', 'text': m.content})
                for tc in m.tool_calls:
                    blocks.append(
                        {
                            'type': 'tool_use',
                            'id': tc.id,
                            'name': tc.name,
                            'input': tc.arguments,
                        }
                    )
                out.append({'role': 'assistant', 'content': blocks})
                continue
            out.append({'role': m.role, 'content': m.content})
        return '\n\n'.join(system_chunks), out

    @_llm_breaker
    def respond(
        self,
        *,
        messages: list[LLMMessage],
        tools: list[Any] | None = None,
        temperature: float = 0.3,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        system, msgs = self._convert(messages)
        kwargs: dict[str, Any] = {
            'model': self.model,
            'messages': msgs,
            'max_tokens': max_tokens,
            'temperature': temperature,
        }
        if system:
            kwargs['system'] = system
        if tools:
            kwargs['tools'] = [t.to_anthropic_schema() for t in tools]
        resp = self._client.messages.create(**kwargs)

        text_chunks: list[str] = []
        tool_calls: list[LLMToolCall] = []
        for block in resp.content or []:
            btype = getattr(block, 'type', '')
            if btype == 'text':
                text_chunks.append(getattr(block, 'text', '') or '')
            elif btype == 'tool_use':
                tool_calls.append(
                    LLMToolCall(
                        id=getattr(block, 'id', ''),
                        name=getattr(block, 'name', ''),
                        arguments=getattr(block, 'input', {}) or {},
                    )
                )
        usage = getattr(resp, 'usage', None)
        return LLMResponse(
            text='\n'.join(text_chunks),
            tool_calls=tool_calls,
            prompt_tokens=getattr(usage, 'input_tokens', 0) or 0,
            completion_tokens=getattr(usage, 'output_tokens', 0) or 0,
            model=self.model,
            raw=resp,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Ollama (best-effort, no native tool calls)
# ─────────────────────────────────────────────────────────────────────────────


class OllamaProvider(LLMProvider):
    name = 'ollama'

    def __init__(self, model: str | None = None) -> None:
        import requests
        from core.agents.provider_registry import get_provider_config

        cfg = get_provider_config('ollama')
        self._requests = requests
        self._api_key = cfg.api_key
        self.base_url = (cfg.base_url or 'http://localhost:11434').rstrip('/')
        self.model = model or cfg.model or 'llama3.2'

    @_llm_breaker
    def respond(
        self,
        *,
        messages: list[LLMMessage],
        tools: list[Any] | None = None,
        temperature: float = 0.3,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        # Best-effort: fold system + history into a single prompt.
        prompt_parts: list[str] = []
        for m in messages:
            tag = m.role.upper()
            prompt_parts.append(f'[{tag}]\n{m.content}')
        prompt = '\n\n'.join(prompt_parts)
        if tools:
            tool_specs = '\n'.join(f'- {t.name}: {t.description}' for t in tools)
            prompt += '\n\n[TOOLS AVAILABLE]\n' + tool_specs
        headers = {'Content-Type': 'application/json'}
        if self._api_key:
            headers['Authorization'] = f'Bearer {self._api_key}'
        resp = self._requests.post(
            f'{self.base_url}/api/generate',
            headers=headers,
            json={
                'model': self.model,
                'prompt': prompt,
                'stream': False,
                'options': {'temperature': temperature, 'num_predict': max_tokens},
            },
            timeout=LLM_HTTP_TIMEOUT_SECS,
        )
        resp.raise_for_status()
        data = resp.json()
        return LLMResponse(text=data.get('response', ''), model=self.model, raw=data)


# ─────────────────────────────────────────────────────────────────────────────
# Gemini — REST, no SDK
# ─────────────────────────────────────────────────────────────────────────────


class GeminiProvider(LLMProvider):
    name = 'gemini'

    def __init__(self, model: str | None = None) -> None:
        import requests
        from core.agents.provider_registry import get_provider_config

        cfg = get_provider_config('gemini')
        if not cfg.api_key:
            raise RuntimeError('Gemini API key not configured')
        self._requests = requests
        self._api_key = cfg.api_key
        self.base_url = (cfg.base_url or 'https://generativelanguage.googleapis.com/v1beta').rstrip(
            '/'
        )
        self.model = model or cfg.model or 'gemini-2.0-flash'

    @_llm_breaker
    def respond(
        self,
        *,
        messages: list[LLMMessage],
        tools: list[Any] | None = None,
        temperature: float = 0.3,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        # Gemini's tool-calling shape differs from OpenAI; we surface tools
        # as a description block in the system prompt for now (best-effort).
        system_chunks: list[str] = []
        contents: list[dict[str, Any]] = []
        for m in messages:
            if m.role == 'system':
                if m.content:
                    system_chunks.append(m.content)
                continue
            role = 'user' if m.role in ('user', 'tool') else 'model'
            contents.append({'role': role, 'parts': [{'text': m.content or ''}]})
        if tools:
            specs = '\n'.join(f'- {t.name}: {t.description}' for t in tools)
            system_chunks.append(f'[TOOLS AVAILABLE]\n{specs}')

        body: dict[str, Any] = {
            'contents': contents,
            'generationConfig': {
                'temperature': temperature,
                'maxOutputTokens': max_tokens,
            },
        }
        if system_chunks:
            body['systemInstruction'] = {'parts': [{'text': '\n\n'.join(system_chunks)}]}

        url = f'{self.base_url}/models/{self.model}:generateContent?key={self._api_key}'
        resp = self._requests.post(url, json=body, timeout=LLM_HTTP_TIMEOUT_SECS)
        resp.raise_for_status()
        data = resp.json()
        chunks: list[str] = []
        for cand in data.get('candidates', []) or []:
            for part in (cand.get('content', {}) or {}).get('parts', []) or []:
                if 'text' in part:
                    chunks.append(part['text'])
        usage = data.get('usageMetadata', {}) or {}
        return LLMResponse(
            text=''.join(chunks),
            prompt_tokens=int(usage.get('promptTokenCount', 0) or 0),
            completion_tokens=int(usage.get('candidatesTokenCount', 0) or 0),
            model=self.model,
            raw=data,
        )


# ─────────────────────────────────────────────────────────────────────────────
# OpenRouter — OpenAI-compatible, just a different base URL
# ─────────────────────────────────────────────────────────────────────────────


class OpenRouterProvider(OpenAIProvider):
    name = 'openrouter'

    def __init__(self, model: str | None = None) -> None:
        from core.agents.provider_registry import get_provider_config

        cfg = get_provider_config('openrouter')
        self._client = _openai_client(
            api_key=cfg.api_key,
            base_url=cfg.base_url or 'https://openrouter.ai/api/v1',
        )
        self.model = model or cfg.model or 'anthropic/claude-3.5-sonnet'


# ─────────────────────────────────────────────────────────────────────────────
# Grok (xAI) — OpenAI-compatible at https://api.x.ai/v1
# ─────────────────────────────────────────────────────────────────────────────


class GrokProvider(OpenAIProvider):
    name = 'grok'

    def __init__(self, model: str | None = None) -> None:
        from core.agents.provider_registry import get_provider_config

        cfg = get_provider_config('grok')
        self._client = _openai_client(
            api_key=cfg.api_key,
            base_url=cfg.base_url or 'https://api.x.ai/v1',
        )
        self.model = model or cfg.model or 'grok-4'


# ─────────────────────────────────────────────────────────────────────────────
# Packy (www.packyapi.com) — Chinese LLM gateway, OpenAI-compatible
# ─────────────────────────────────────────────────────────────────────────────


class PackyProvider(OpenAIProvider):
    name = 'packy'

    def __init__(self, model: str | None = None) -> None:
        from core.agents.provider_registry import get_provider_config

        cfg = get_provider_config('packy')
        self._client = _openai_client(
            api_key=cfg.api_key,
            base_url=cfg.base_url or 'https://www.packyapi.com/v1',
        )
        self.model = model or cfg.model or 'claude-3-5-sonnet-20241022'


# ─────────────────────────────────────────────────────────────────────────────
# Hermes (NousResearch) — Hermes 3/4, native function-calling. OpenAI-compatible;
# defaults to the OpenRouter gateway (point base_url at Nous's own inference API
# instead via the AI Providers panel).
# ─────────────────────────────────────────────────────────────────────────────


class HermesProvider(OpenAIProvider):
    name = 'hermes'

    def __init__(self, model: str | None = None) -> None:
        from core.agents.provider_registry import get_provider_config

        cfg = get_provider_config('hermes')
        self._client = _openai_client(
            api_key=cfg.api_key,
            base_url=cfg.base_url or 'https://openrouter.ai/api/v1',
        )
        self.model = model or cfg.model or 'nousresearch/hermes-3-llama-3.1-405b'


# ─────────────────────────────────────────────────────────────────────────────
# apikey.fun — unified OpenAI-compatible gateway to many model vendors.
# ─────────────────────────────────────────────────────────────────────────────


class ApikeyProvider(OpenAIProvider):
    name = 'apikey'

    def __init__(self, model: str | None = None) -> None:
        from core.agents.provider_registry import get_provider_config

        cfg = get_provider_config('apikey')
        self._client = _openai_client(
            api_key=cfg.api_key,
            base_url=cfg.base_url or 'https://api.apikey.fun/v1',
        )
        self.model = model or cfg.model or 'gpt-4o-mini'


# ─────────────────────────────────────────────────────────────────────────────
# DeepSeek — OpenAI-compatible API (deepseek-chat / deepseek-reasoner).
# ─────────────────────────────────────────────────────────────────────────────


class DeepSeekProvider(OpenAIProvider):
    name = 'deepseek'

    def __init__(self, model: str | None = None) -> None:
        from core.agents.provider_registry import get_provider_config

        cfg = get_provider_config('deepseek')
        self._client = _openai_client(
            api_key=cfg.api_key,
            base_url=cfg.base_url or 'https://api.deepseek.com',
        )
        self.model = model or cfg.model or 'deepseek-chat'


# ─────────────────────────────────────────────────────────────────────────────
# Mock — deterministic, used in tests + when no provider configured
# ─────────────────────────────────────────────────────────────────────────────


class MockLLMProvider(LLMProvider):
    """Scripted provider for tests.

    Construct with a list of `LLMResponse` objects; each `respond()` call
    pops the next response. Useful for asserting tool-call sequences.
    """

    name = 'mock'

    def __init__(
        self,
        responses: Iterable[LLMResponse] | None = None,
        *,
        echo_user: bool = True,
    ) -> None:
        self.model = 'mock-1'
        self._responses: list[LLMResponse] = list(responses or [])
        self._echo_user = echo_user
        self.calls: list[dict[str, Any]] = []

    def push(self, response: LLMResponse) -> None:
        self._responses.append(response)

    def respond(
        self,
        *,
        messages: list[LLMMessage],
        tools: list[Any] | None = None,
        temperature: float = 0.3,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        self.calls.append({'messages': list(messages), 'tools': list(tools or [])})
        if self._responses:
            r = self._responses.pop(0)
            r.model = r.model or self.model
            return r
        if self._echo_user:
            last_user = next((m.content for m in reversed(messages) if m.role == 'user'), '')
            return LLMResponse(text=f'OK: {last_user[:200]}', model=self.model)
        return LLMResponse(text='', model=self.model)


# ─────────────────────────────────────────────────────────────────────────────
# Factory
# ─────────────────────────────────────────────────────────────────────────────


_PROVIDER_CLASSES: dict[str, type[LLMProvider]] = {
    'openai': OpenAIProvider,
    'anthropic': AnthropicProvider,
    'ollama': OllamaProvider,
    'gemini': GeminiProvider,
    'openrouter': OpenRouterProvider,
    'grok': GrokProvider,
    'packy': PackyProvider,
    'hermes': HermesProvider,
    'apikey': ApikeyProvider,
    'deepseek': DeepSeekProvider,
}


class FallbackProviderRouter(LLMProvider):
    """
    Automated Fallback Router to ensure 99.9% uptime.
    Wraps multiple providers and cascades through them if one is degraded
    or its circuit breaker is open.
    """

    name = 'fallback_router'

    def __init__(self, primary: LLMProvider, secondaries: list[LLMProvider]):
        self.primary = primary
        self.secondaries = secondaries
        self.model = primary.model

    def respond(
        self,
        *,
        messages: list[LLMMessage],
        tools: list[Any] | None = None,
        temperature: float = 0.3,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        providers_to_try = [self.primary] + self.secondaries
        last_error_text = ''

        for provider in providers_to_try:
            resp = provider.respond(
                messages=messages,
                tools=tools,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            # Check if the circuit breaker tripped or there was a degradation error
            if '[Upstream AI provider is degraded' not in resp.text:
                return resp
            last_error_text = resp.text
            logger.info('FallbackRouter: Provider %s degraded, trying next.', provider.name)

        return LLMResponse(
            text=f'[All AI providers degraded. Last error: {last_error_text}]',
            model='fallback_router_failed',
        )


def get_llm_provider(
    name: str | None = None, *, model: str | None = None, use_fallback: bool = True
) -> LLMProvider:
    """Resolve the active provider. Reads the ai_assistant plugin config (so
    keys saved in the dashboard apply immediately, no restart). Falls back
    to `MockLLMProvider` when nothing is configured.
    If use_fallback is True, it wraps the primary provider in a FallbackProviderRouter
    with secondary providers to ensure 99.9% uptime."""
    if name:
        chosen = name.strip().lower()
    else:
        try:
            from core.agents.provider_registry import get_active_provider_name

            chosen = get_active_provider_name()
        except Exception:  # noqa: BLE001 — registry not ready (early boot, tests)
            chosen = (getattr(settings, 'AI_PROVIDER', '') or '').strip().lower()

    cls = _PROVIDER_CLASSES.get(chosen)
    if cls is None:
        return _make_unconfigured_mock(
            f'No AI provider selected. Open Settings → AI providers and pick one.'
        )
    try:
        primary = cls(model=model)

        if not use_fallback:
            return primary

        # Automated fallback configuration
        # Attempt to instantiate fallback providers if they are configured
        secondaries = []
        fallback_choices = ['anthropic', 'openai', 'gemini']
        fallback_choices = [c for c in fallback_choices if c != chosen]

        for fallback_name in fallback_choices:
            fallback_cls = _PROVIDER_CLASSES.get(fallback_name)
            try:
                # Instantiating might fail if no API key is configured
                secondary = fallback_cls()
                # Check if it has a valid API key config by verifying it didn't throw
                # Some providers like Gemini throw if no key. Others might just pass empty strings.
                if getattr(secondary, '_api_key', None) or hasattr(secondary, '_client'):
                    # Basic check if it has client initialized
                    secondaries.append(secondary)
            except Exception:  # noqa: S110 — fallback provider is optional; skip if unconfigured
                pass

        if secondaries:
            return FallbackProviderRouter(primary, secondaries)
        return primary

    except Exception as e:  # noqa: BLE001
        logger.warning('%s provider unavailable, using mock: %s', chosen, e)
        return _make_unconfigured_mock(
            f'AI provider {chosen!r} is selected but its API key is missing or '
            f'invalid. Open Settings → AI providers, paste a real key, and click '
            f'Save. (Underlying error: {e})'
        )


class _UnconfiguredProvider(LLMProvider):
    """Returns a fixed help message every time. Used when the real provider
    can't be constructed — surfaces config guidance to the dashboard chat
    instead of echoing the user's input."""

    name = 'unconfigured'

    def __init__(self, message: str) -> None:
        self.model = 'unconfigured'
        self._message = message

    def respond(
        self,
        *,
        messages: list[LLMMessage],
        tools: list[Any] | None = None,
        temperature: float = 0.3,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        return LLMResponse(text=self._message, model=self.model)


def _make_unconfigured_mock(message: str) -> LLMProvider:
    return _UnconfiguredProvider(message)
