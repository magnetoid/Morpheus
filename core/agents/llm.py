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
from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Iterable

from django.conf import settings

logger = logging.getLogger('morpheus.agents.llm')


@dataclass(slots=True)
class LLMMessage:
    role: str            # 'system' | 'user' | 'assistant' | 'tool'
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
    ) -> LLMResponse:
        ...


# ─────────────────────────────────────────────────────────────────────────────
# OpenAI
# ─────────────────────────────────────────────────────────────────────────────


class OpenAIProvider(LLMProvider):
    name = 'openai'

    def __init__(self, model: str | None = None) -> None:
        import openai  # lazy import — provider is only loaded when used
        from plugins.installed.ai_assistant.services.config import get_provider_config
        cfg = get_provider_config('openai')
        kwargs: dict[str, Any] = {}
        if cfg.api_key:
            kwargs['api_key'] = cfg.api_key
        if cfg.base_url and cfg.base_url != 'https://api.openai.com/v1':
            kwargs['base_url'] = cfg.base_url
        self._client = openai.OpenAI(**kwargs) if kwargs else openai.OpenAI()
        self.model = model or cfg.model or 'gpt-4o-mini'

    def _convert_messages(self, messages: list[LLMMessage]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for m in messages:
            if m.role == 'tool':
                out.append({
                    'role': 'tool',
                    'tool_call_id': m.tool_call_id or '',
                    'content': m.content,
                })
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
        for tc in (getattr(msg, 'tool_calls', None) or []):
            try:
                args = json.loads(tc.function.arguments or '{}')
            except json.JSONDecodeError:
                args = {}
            tool_calls.append(LLMToolCall(id=tc.id, name=tc.function.name, arguments=args))
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
        from plugins.installed.ai_assistant.services.config import get_provider_config
        cfg = get_provider_config('anthropic')
        self._client = (
            anthropic.Anthropic(api_key=cfg.api_key) if cfg.api_key else anthropic.Anthropic()
        )
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
                out.append({
                    'role': 'user',
                    'content': [{
                        'type': 'tool_result',
                        'tool_use_id': m.tool_call_id or '',
                        'content': m.content,
                    }],
                })
                continue
            if m.role == 'assistant' and m.tool_calls:
                blocks: list[dict[str, Any]] = []
                if m.content:
                    blocks.append({'type': 'text', 'text': m.content})
                for tc in m.tool_calls:
                    blocks.append({
                        'type': 'tool_use',
                        'id': tc.id,
                        'name': tc.name,
                        'input': tc.arguments,
                    })
                out.append({'role': 'assistant', 'content': blocks})
                continue
            out.append({'role': m.role, 'content': m.content})
        return '\n\n'.join(system_chunks), out

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
                tool_calls.append(LLMToolCall(
                    id=getattr(block, 'id', ''),
                    name=getattr(block, 'name', ''),
                    arguments=getattr(block, 'input', {}) or {},
                ))
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
        from plugins.installed.ai_assistant.services.config import get_provider_config
        cfg = get_provider_config('ollama')
        self._requests = requests
        self._api_key = cfg.api_key
        self.base_url = (cfg.base_url or 'http://localhost:11434').rstrip('/')
        self.model = model or cfg.model or 'llama3.2'

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
            timeout=120,
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
        from plugins.installed.ai_assistant.services.config import get_provider_config
        cfg = get_provider_config('gemini')
        if not cfg.api_key:
            raise RuntimeError('Gemini API key not configured')
        self._requests = requests
        self._api_key = cfg.api_key
        self.base_url = (cfg.base_url or 'https://generativelanguage.googleapis.com/v1beta').rstrip('/')
        self.model = model or cfg.model or 'gemini-2.0-flash'

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
        resp = self._requests.post(url, json=body, timeout=120)
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
        import openai
        from plugins.installed.ai_assistant.services.config import get_provider_config
        cfg = get_provider_config('openrouter')
        kwargs: dict[str, Any] = {}
        if cfg.api_key:
            kwargs['api_key'] = cfg.api_key
        kwargs['base_url'] = cfg.base_url or 'https://openrouter.ai/api/v1'
        self._client = openai.OpenAI(**kwargs)
        self.model = model or cfg.model or 'anthropic/claude-3.5-sonnet'


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
}


def get_llm_provider(name: str | None = None, *, model: str | None = None) -> LLMProvider:
    """Resolve the active provider. Reads the ai_assistant plugin config (so
    keys saved in the dashboard apply immediately, no restart). Falls back
    to `MockLLMProvider` when nothing is configured."""
    if name:
        chosen = name.strip().lower()
    else:
        try:
            from plugins.installed.ai_assistant.services.config import get_active_provider_name
            chosen = get_active_provider_name()
        except Exception:  # noqa: BLE001 — registry not ready (early boot, tests)
            chosen = (getattr(settings, 'AI_PROVIDER', '') or '').strip().lower()

    cls = _PROVIDER_CLASSES.get(chosen)
    if cls is None:
        return MockLLMProvider()
    try:
        return cls(model=model)
    except Exception as e:  # noqa: BLE001
        logger.warning('%s provider unavailable, using mock: %s', chosen, e)
        return MockLLMProvider()
