"""
AI Assistant — LLM Gateway
Swappable provider: OpenAI | Anthropic | Gemini | OpenRouter | Grok | Packy | Ollama
Every call is automatically logged to AIInteraction.

All providers source their api keys / base URLs / models from the
ai_assistant plugin config (dashboard) via
``plugins.installed.ai_assistant.services.config.get_provider_config``.
Env vars remain a fallback for local dev.
"""

import logging
import time
from abc import ABC, abstractmethod

import requests

from plugins.installed.ai_assistant.services.config import (
    ProviderConfig,
    get_active_provider_name,
    get_provider_config,
)

logger = logging.getLogger('morpheus.ai.llm')


class LLMGateway(ABC):
    """Abstract base — all providers implement this interface."""

    model: str = ''

    @abstractmethod
    def complete(
        self,
        prompt: str,
        system: str = '',
        temperature: float = 0.7,
        max_tokens: int = 1000,
        **kwargs,
    ) -> str: ...

    @abstractmethod
    def embed(self, text: str) -> list[float]: ...

    def stream(self, prompt: str, system: str = '', **kwargs):
        """Default: non-streaming fallback."""
        yield self.complete(prompt, system=system, **kwargs)

    def _log(
        self,
        interaction_type: str,
        prompt: str,
        result: str,
        prompt_tokens: int,
        completion_tokens: int,
        cost_usd: float,
        latency_ms: int,
        success: bool = True,
        error: str = '',
        **context,
    ):
        """Log every AI call to AIInteraction. Never raises."""
        try:
            from plugins.installed.ai_assistant.models import AIInteraction

            AIInteraction.objects.create(
                interaction_type=interaction_type,
                model_used=self.model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
                cost_usd=cost_usd,
                latency_ms=latency_ms,
                input_data={'prompt': prompt[:2000]},
                output_data={'result': result[:2000]},
                success=success,
                error_message=error,
                **{
                    k: v
                    for k, v in context.items()
                    if k in ('customer', 'product', 'order', 'agent_id')
                },
            )
        except Exception as e:
            logger.error(f'Failed to log AIInteraction: {e}')


class OpenAIGateway(LLMGateway):
    """OpenAI Chat Completions. Also covers OpenAI-compatible endpoints
    when a custom base_url is configured (LM Studio, vLLM, etc.)."""

    def __init__(self, cfg: ProviderConfig | None = None):
        # Shared timeout policy with core.agents.llm — keep a single
        # source of truth.
        from core.agents.llm import _openai_client

        cfg = cfg or get_provider_config('openai')
        base = cfg.base_url if cfg.base_url and cfg.base_url != 'https://api.openai.com/v1' else ''
        self.client = _openai_client(api_key=cfg.api_key, base_url=base)
        self.model = cfg.model or 'gpt-4o-mini'
        self.embed_model = cfg.embedding_model

    def complete(
        self,
        prompt: str,
        system: str = '',
        temperature: float = 0.7,
        max_tokens: int = 1000,
        **kwargs,
    ) -> str:
        messages = []
        if system:
            messages.append({'role': 'system', 'content': system})
        messages.append({'role': 'user', 'content': prompt})

        start = time.monotonic()
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            result = response.choices[0].message.content or ''
            elapsed = int((time.monotonic() - start) * 1000)
            usage = response.usage
            cost = self._estimate_cost(
                getattr(usage, 'prompt_tokens', 0) or 0,
                getattr(usage, 'completion_tokens', 0) or 0,
            )
            self._log(
                'completion',
                prompt,
                result,
                getattr(usage, 'prompt_tokens', 0) or 0,
                getattr(usage, 'completion_tokens', 0) or 0,
                cost,
                elapsed,
            )
            return result
        except Exception as e:
            elapsed = int((time.monotonic() - start) * 1000)
            self._log('completion', prompt, '', 0, 0, 0, elapsed, success=False, error=str(e))
            logger.error(f'OpenAI completion error: {e}')
            raise

    def embed(self, text: str) -> list[float]:
        response = self.client.embeddings.create(model=self.embed_model, input=text)
        return response.data[0].embedding

    def _estimate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        prices = {
            'gpt-4o': (0.005, 0.015),
            'gpt-4o-mini': (0.00015, 0.0006),
            'gpt-3.5-turbo': (0.0005, 0.0015),
        }
        p_in, p_out = prices.get(self.model, (0.001, 0.003))
        return (prompt_tokens / 1000 * p_in) + (completion_tokens / 1000 * p_out)


class AnthropicGateway(LLMGateway):
    def __init__(self, cfg: ProviderConfig | None = None):
        import anthropic

        cfg = cfg or get_provider_config('anthropic')
        kwargs: dict = {}
        if cfg.api_key:
            kwargs['api_key'] = cfg.api_key
        # Honour a custom endpoint (packy / a proxy / a Bedrock-style gateway).
        # The Anthropic SDK appends /v1/messages itself, so strip a trailing
        # /v1 and never pass the public default.
        base = (cfg.base_url or '').rstrip('/')
        if base.endswith('/v1'):
            base = base[: -len('/v1')]
        if base and base != 'https://api.anthropic.com':
            kwargs['base_url'] = base
        self.client = anthropic.Anthropic(**kwargs)
        self.model = cfg.model or 'claude-3-5-sonnet-latest'

    def complete(
        self,
        prompt: str,
        system: str = '',
        temperature: float = 0.7,
        max_tokens: int = 1000,
        **kwargs,
    ) -> str:
        start = time.monotonic()
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=system or 'You are a helpful ecommerce assistant.',
                messages=[{'role': 'user', 'content': prompt}],
                temperature=temperature,
            )
            result = response.content[0].text
            elapsed = int((time.monotonic() - start) * 1000)
            self._log(
                'completion',
                prompt,
                result,
                response.usage.input_tokens,
                response.usage.output_tokens,
                0.0,
                elapsed,
            )
            return result
        except Exception as e:
            elapsed = int((time.monotonic() - start) * 1000)
            self._log('completion', prompt, '', 0, 0, 0, elapsed, success=False, error=str(e))
            raise

    def embed(self, text: str) -> list[float]:
        # Fall through to OpenAI for embeddings when available.
        oa = get_provider_config('openai')
        if oa.api_key:
            return OpenAIGateway(oa).embed(text)
        raise NotImplementedError(
            'Anthropic does not provide embeddings. Configure an OpenAI key '
            'in AI providers, or use Ollama/Gemini.'
        )


class GeminiGateway(LLMGateway):
    """Google Gemini via REST. Avoids extra SDK dependency."""

    def __init__(self, cfg: ProviderConfig | None = None):
        cfg = cfg or get_provider_config('gemini')
        self.api_key = cfg.api_key
        self.base_url = (cfg.base_url or 'https://generativelanguage.googleapis.com/v1beta').rstrip(
            '/'
        )
        self.model = cfg.model or 'gemini-2.0-flash'

    def complete(
        self,
        prompt: str,
        system: str = '',
        temperature: float = 0.7,
        max_tokens: int = 1000,
        **kwargs,
    ) -> str:
        if not self.api_key:
            raise RuntimeError('Gemini API key not configured.')
        start = time.monotonic()
        url = f'{self.base_url}/models/{self.model}:generateContent?key={self.api_key}'
        body = {
            'contents': [{'role': 'user', 'parts': [{'text': prompt}]}],
            'generationConfig': {
                'temperature': temperature,
                'maxOutputTokens': max_tokens,
            },
        }
        if system:
            body['systemInstruction'] = {'parts': [{'text': system}]}
        try:
            resp = requests.post(url, json=body, timeout=20)
            resp.raise_for_status()
            data = resp.json()
            chunks = []
            for cand in data.get('candidates', []) or []:
                for part in (cand.get('content', {}) or {}).get('parts', []) or []:
                    if 'text' in part:
                        chunks.append(part['text'])
            result = ''.join(chunks)
            elapsed = int((time.monotonic() - start) * 1000)
            usage = data.get('usageMetadata', {}) or {}
            self._log(
                'completion',
                prompt,
                result,
                int(usage.get('promptTokenCount', 0) or 0),
                int(usage.get('candidatesTokenCount', 0) or 0),
                0.0,
                elapsed,
            )
            return result
        except Exception as e:
            elapsed = int((time.monotonic() - start) * 1000)
            self._log('completion', prompt, '', 0, 0, 0, elapsed, success=False, error=str(e))
            raise

    def embed(self, text: str) -> list[float]:
        if not self.api_key:
            raise RuntimeError('Gemini API key not configured.')
        embed_model = 'text-embedding-004'
        url = f'{self.base_url}/models/{embed_model}:embedContent?key={self.api_key}'
        resp = requests.post(
            url,
            json={
                'content': {'parts': [{'text': text}]},
            },
            timeout=30,
        )
        resp.raise_for_status()
        return list((resp.json().get('embedding') or {}).get('values') or [])


class OpenRouterGateway(OpenAIGateway):
    """OpenRouter is OpenAI-API-compatible — reuse the OpenAI client with
    a custom base_url."""

    def __init__(self, cfg: ProviderConfig | None = None):
        cfg = cfg or get_provider_config('openrouter')
        # OpenRouter has no embeddings — surface that early on .embed().
        if not cfg.base_url:
            cfg.base_url = 'https://openrouter.ai/api/v1'
        super().__init__(cfg)

    def embed(self, text: str) -> list[float]:
        oa = get_provider_config('openai')
        if oa.api_key:
            return OpenAIGateway(oa).embed(text)
        raise NotImplementedError(
            'OpenRouter does not provide embeddings. Configure OpenAI or Ollama.'
        )


class GrokGateway(OpenAIGateway):
    """xAI's Grok exposes an OpenAI-compatible Chat Completions API at
    https://api.x.ai/v1 — same client, different base URL + model."""

    def __init__(self, cfg: ProviderConfig | None = None):
        cfg = cfg or get_provider_config('grok')
        if not cfg.base_url:
            cfg.base_url = 'https://api.x.ai/v1'
        super().__init__(cfg)

    def embed(self, text: str) -> list[float]:
        # xAI hasn't shipped a public embeddings endpoint as of May 2026.
        # Fall back to OpenAI's embeddings if a key is configured.
        oa = get_provider_config('openai')
        if oa.api_key:
            return OpenAIGateway(oa).embed(text)
        raise NotImplementedError(
            'Grok (xAI) has no embeddings endpoint. Configure OpenAI or Ollama for embeddings.'
        )


class ApikeyFunGateway(OpenAIGateway):
    """apikey.fun — a unified LLM gateway exposing an OpenAI-compatible Chat
    Completions API at https://api.apikey.fun/v1 (proxies GPT / Claude / Gemini
    / … through one endpoint). Same client, different base URL + model."""

    def __init__(self, cfg: ProviderConfig | None = None):
        cfg = cfg or get_provider_config('apikey')
        if not cfg.base_url:
            cfg.base_url = 'https://api.apikey.fun/v1'
        super().__init__(cfg)

    def embed(self, text: str) -> list[float]:
        oa = get_provider_config('openai')
        if oa.api_key:
            return OpenAIGateway(oa).embed(text)
        raise NotImplementedError('apikey.fun: configure OpenAI or Ollama for embeddings.')


class PackyGateway(AnthropicGateway):
    """Packy (www.packyapi.com) via its Anthropic-compatible Messages API — a
    unified gateway that serves Claude (and other) models. Set the API key,
    optional base URL, and a Claude model in Settings → AI providers. base_url
    defaults to packy's root (the Anthropic SDK appends /v1/messages).
    Embeddings fall back to OpenAI/Ollama via AnthropicGateway.embed."""

    def __init__(self, cfg: ProviderConfig | None = None):
        cfg = cfg or get_provider_config('packy')
        if not cfg.base_url:
            cfg.base_url = 'https://www.packyapi.com'
        super().__init__(cfg)


class OllamaGateway(LLMGateway):
    """Local Ollama instance — full privacy, no data leaves the server."""

    def __init__(self, cfg: ProviderConfig | None = None):
        cfg = cfg or get_provider_config('ollama')
        self.base_url = (cfg.base_url or 'http://localhost:11434').rstrip('/')
        self.api_key = cfg.api_key
        self.model = cfg.model or 'llama3.2'

    def _headers(self) -> dict:
        h = {'Content-Type': 'application/json'}
        if self.api_key:
            h['Authorization'] = f'Bearer {self.api_key}'
        return h

    def complete(
        self,
        prompt: str,
        system: str = '',
        temperature: float = 0.7,
        max_tokens: int = 1000,
        **kwargs,
    ) -> str:
        start = time.monotonic()
        try:
            resp = requests.post(
                f'{self.base_url}/api/generate',
                headers=self._headers(),
                json={
                    'model': self.model,
                    'prompt': f'{system}\n\n{prompt}' if system else prompt,
                    'stream': False,
                    'options': {'temperature': temperature, 'num_predict': max_tokens},
                },
                timeout=20,
            )
            resp.raise_for_status()
            result = resp.json().get('response', '')
            elapsed = int((time.monotonic() - start) * 1000)
            self._log('completion', prompt, result, 0, 0, 0.0, elapsed)
            return result
        except Exception as e:
            logger.error(f'Ollama error: {e}')
            raise

    def embed(self, text: str) -> list[float]:
        resp = requests.post(
            f'{self.base_url}/api/embeddings',
            headers=self._headers(),
            json={'model': self.model, 'prompt': text},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json().get('embedding', [])


_GATEWAYS = {
    'openai': OpenAIGateway,
    'anthropic': AnthropicGateway,
    'gemini': GeminiGateway,
    'openrouter': OpenRouterGateway,
    'grok': GrokGateway,
    'apikey': ApikeyFunGateway,
    'packy': PackyGateway,
    'ollama': OllamaGateway,
}


def get_llm() -> LLMGateway:
    """Factory — returns a gateway for the active provider chosen in
    the AI Providers settings panel (env fallback for legacy installs)."""
    provider = get_active_provider_name()
    cls = _GATEWAYS.get(provider)
    if not cls:
        raise ValueError(f'Unknown AI provider: {provider!r}. Choose: {list(_GATEWAYS.keys())}')
    return cls()
