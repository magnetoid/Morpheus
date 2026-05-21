"""Provider probe — fetch a list of available models from each AI provider.

This is a thin HTTP client that lets the dashboard "Fetch models" button
populate a real model dropdown instead of asking merchants to type a
model id by hand. Also serves as a connection test: if the request
succeeds we know the API key works.

Each ``probe_<provider>`` returns a uniform shape::

    {
        'ok': bool,
        'models': [{'id': 'gpt-4o-mini', 'label': 'gpt-4o-mini'}],
        'error': str | None,   # only when ok=False
    }

Network calls have a hard 8s timeout so a misconfigured/unreachable
provider can't hang the dashboard.
"""
from __future__ import annotations

import json
import logging
from typing import Any
from urllib import error as urlerror
from urllib import request as urlrequest

logger = logging.getLogger('morpheus.ai_assistant.probe')

_TIMEOUT = 8


def _http_get(url: str, headers: dict[str, str]) -> dict[str, Any]:
    req = urlrequest.Request(url, headers=headers, method='GET')
    try:
        with urlrequest.urlopen(req, timeout=_TIMEOUT) as resp:
            body = resp.read().decode('utf-8', errors='replace')
            if resp.status >= 400:
                return {'_error': f'HTTP {resp.status}: {body[:200]}'}
            try:
                return json.loads(body)
            except json.JSONDecodeError:
                return {'_error': f'non-JSON response: {body[:200]}'}
    except urlerror.HTTPError as e:
        body = ''
        try:
            body = e.read().decode('utf-8', errors='replace')[:200]
        except Exception:  # noqa: BLE001
            pass
        return {'_error': f'HTTP {e.code}: {body or e.reason}'}
    except urlerror.URLError as e:
        return {'_error': f'connection error: {e.reason}'}
    except Exception as e:  # noqa: BLE001
        return {'_error': f'request failed: {e}'}


def _ok(models: list[dict]) -> dict[str, Any]:
    return {'ok': True, 'models': models, 'error': None}


def _fail(error: str) -> dict[str, Any]:
    return {'ok': False, 'models': [], 'error': error}


# ── OpenAI ───────────────────────────────────────────────────────────────────


def probe_openai(*, api_key: str, base_url: str = '') -> dict:
    if not api_key:
        return _fail('OpenAI API key not set.')
    base = (base_url or 'https://api.openai.com/v1').rstrip('/')
    data = _http_get(f'{base}/models', headers={'Authorization': f'Bearer {api_key}'})
    if '_error' in data:
        return _fail(str(data['_error']))
    items = data.get('data') or []
    models = [
        {'id': m.get('id'), 'label': m.get('id')}
        for m in items if m.get('id')
    ]
    models.sort(key=lambda m: m['id'])
    return _ok(models)


# ── Anthropic ────────────────────────────────────────────────────────────────


def probe_anthropic(*, api_key: str, base_url: str = '') -> dict:
    if not api_key:
        return _fail('Anthropic API key not set.')
    base = (base_url or 'https://api.anthropic.com/v1').rstrip('/')
    data = _http_get(
        f'{base}/models',
        headers={
            'x-api-key': api_key,
            'anthropic-version': '2023-06-01',
        },
    )
    if '_error' in data:
        return _fail(str(data['_error']))
    items = data.get('data') or []
    models = [
        {'id': m.get('id'), 'label': m.get('display_name') or m.get('id')}
        for m in items if m.get('id')
    ]
    models.sort(key=lambda m: m['id'])
    return _ok(models)


# ── Google Gemini ────────────────────────────────────────────────────────────


def probe_gemini(*, api_key: str, base_url: str = '') -> dict:
    if not api_key:
        return _fail('Gemini API key not set.')
    base = (base_url or 'https://generativelanguage.googleapis.com/v1beta').rstrip('/')
    # Gemini uses ?key=… instead of an Authorization header.
    data = _http_get(f'{base}/models?key={api_key}', headers={})
    if '_error' in data:
        return _fail(str(data['_error']))
    items = data.get('models') or []
    models = []
    for m in items:
        # 'name' looks like 'models/gemini-2.0-flash' — strip the prefix.
        full = m.get('name', '')
        mid = full.split('/', 1)[1] if '/' in full else full
        if not mid:
            continue
        if 'generateContent' not in (m.get('supportedGenerationMethods') or []):
            continue
        models.append({'id': mid, 'label': m.get('displayName') or mid})
    models.sort(key=lambda m: m['id'])
    return _ok(models)


# ── OpenRouter ───────────────────────────────────────────────────────────────


def probe_openrouter(*, api_key: str, base_url: str = '') -> dict:
    # OpenRouter publishes its model catalog without auth, but we still
    # require a key here so this doubles as a connection test.
    if not api_key:
        return _fail('OpenRouter API key not set.')
    base = (base_url or 'https://openrouter.ai/api/v1').rstrip('/')
    data = _http_get(
        f'{base}/models',
        headers={'Authorization': f'Bearer {api_key}'},
    )
    if '_error' in data:
        return _fail(str(data['_error']))
    items = data.get('data') or []
    models = [
        {'id': m.get('id'), 'label': m.get('name') or m.get('id')}
        for m in items if m.get('id')
    ]
    models.sort(key=lambda m: m['id'])
    return _ok(models)


# ── Grok (xAI) — OpenAI-compatible at https://api.x.ai/v1 ───────────────────


def probe_grok(*, api_key: str, base_url: str = '') -> dict:
    if not api_key:
        return _fail('Grok API key not set.')
    base = (base_url or 'https://api.x.ai/v1').rstrip('/')
    data = _http_get(
        f'{base}/models',
        headers={'Authorization': f'Bearer {api_key}'},
    )
    if '_error' in data:
        return _fail(str(data['_error']))
    items = data.get('data') or []
    models = [
        {'id': m.get('id'), 'label': m.get('id')}
        for m in items if m.get('id')
    ]
    models.sort(key=lambda m: m['id'])
    return _ok(models)


# ── Packy (packiapi.com) — OpenAI-compatible Chinese LLM gateway ────────────


def probe_packy(*, api_key: str, base_url: str = '') -> dict:
    if not api_key:
        return _fail('Packy API key not set.')
    base = (base_url or 'https://packiapi.com/v1').rstrip('/')
    data = _http_get(
        f'{base}/models',
        headers={'Authorization': f'Bearer {api_key}'},
    )
    if '_error' in data:
        return _fail(str(data['_error']))
    items = data.get('data') or []
    models = [
        {'id': m.get('id'), 'label': m.get('id')}
        for m in items if m.get('id')
    ]
    models.sort(key=lambda m: m['id'])
    return _ok(models)


# ── Ollama (cloud or self-hosted) ────────────────────────────────────────────


def probe_ollama(*, api_key: str = '', base_url: str = '') -> dict:
    base = (base_url or 'http://localhost:11434').rstrip('/')
    headers = {}
    if api_key:
        headers['Authorization'] = f'Bearer {api_key}'
    data = _http_get(f'{base}/api/tags', headers=headers)
    if '_error' in data:
        return _fail(str(data['_error']))
    items = data.get('models') or []
    models = [
        {'id': m.get('name'), 'label': m.get('name')}
        for m in items if m.get('name')
    ]
    models.sort(key=lambda m: m['id'])
    return _ok(models)


_PROBES = {
    'openai': probe_openai,
    'anthropic': probe_anthropic,
    'gemini': probe_gemini,
    'openrouter': probe_openrouter,
    'grok': probe_grok,
    'packy': probe_packy,
    'ollama': probe_ollama,
}


def probe(provider: str, *, api_key: str = '', base_url: str = '') -> dict:
    fn = _PROBES.get(provider)
    if fn is None:
        return _fail(f'unknown provider: {provider}')
    try:
        return fn(api_key=api_key, base_url=base_url)
    except Exception as e:  # noqa: BLE001 — never bubble; surface in dashboard
        logger.warning('probe %s failed: %s', provider, e, exc_info=True)
        return _fail(f'unhandled error: {e}')
