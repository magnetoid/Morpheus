"""Linda's per-page helper: turn what's on a dashboard page into a short
explanation + advice. No tools → the LLM layer's 1h cache applies, so repeat
views of unchanged pages are free."""

from __future__ import annotations

import json
import logging
import re

logger = logging.getLogger('morpheus.assistant')

_SYSTEM = (
    'You are Linda, the in-dashboard assistant for a Morpheus e-commerce store. '
    'A merchant is looking at a dashboard page. Using ONLY the page content given, '
    'explain it plainly and advise. Be concise, warm, and concrete. '
    'Respond with STRICT JSON, no prose, in this shape: '
    '{"summary": "1-2 sentences on what this page is for", '
    '"numbers": [{"label": "metric name", "reading": "what the value means in plain words"}], '
    '"actions": ["a concrete next step", "..."]}. '
    'Use at most 4 numbers and 3 actions. If the page has no meaningful data, '
    'return {"summary": "", "numbers": [], "actions": []}.'
)

_MIN_TEXT = 3  # below this the page is effectively empty — skip the LLM


def _parse_json(text: str) -> dict | None:
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    m = re.search(r'\{.*\}', text, re.DOTALL)  # first {...} block
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            return None
    return None


def build_page_help(context: dict, provider=None) -> dict:
    fail = {'ok': False, 'summary': '', 'numbers': [], 'actions': [], 'message': ''}
    page_text = (context.get('page_text') or '').strip()
    if len(page_text) < _MIN_TEXT:
        return {**fail, 'message': 'Not enough on this page to explain.'}

    if provider is None:
        from core.assistant.providers import get_default_provider

        provider = get_default_provider()

    from core.agents.llm import LLMMessage

    user = (
        f'Page title: {context.get("page_title") or "Dashboard"}\n'
        f'Page URL: {context.get("page_url") or ""}\n'
    )
    structured = context.get('structured')
    if structured:
        user += f'Structured data: {json.dumps(structured)[:2000]}\n'
    user += f'Visible page text:\n{page_text[:4000]}'

    try:
        resp = provider.respond(
            messages=[
                LLMMessage(role='system', content=_SYSTEM),
                LLMMessage(role='user', content=user),
            ],
            tools=None,
            temperature=0.2,
            max_tokens=700,
        )
    except Exception as e:  # noqa: BLE001 — provider/breaker safety net
        logger.warning('page_help: provider call failed: %s', e, exc_info=True)
        return {**fail, 'message': 'Linda is unavailable right now.'}

    data = _parse_json(getattr(resp, 'text', '') or '')
    if not isinstance(data, dict):
        return {**fail, 'message': 'Linda could not read this page.'}

    return {
        'ok': True,
        'summary': str(data.get('summary') or ''),
        'numbers': [
            {'label': str(n.get('label', '')), 'reading': str(n.get('reading', ''))}
            for n in (data.get('numbers') or [])[:4]
            if isinstance(n, dict)
        ],
        'actions': [str(a) for a in (data.get('actions') or [])[:3]],
        'message': '',
    }
