"""Templatetags for inline AI affordances in admin pages.

Usage in any admin template:

    {% load morph_assistant %}
    {% morph_ask context_label="this order" prefill="investigate order #1234" %}

Renders a small "Ask Linda" button. Click → opens the floating Linda
panel with the prefill pre-typed in. Pre-fills are URL-aware when the
templatetag is invoked without args:

    {% morph_ask %}      ← auto-derives context from request.path
"""
from __future__ import annotations

import re

from django import template
from django.utils.safestring import mark_safe

register = template.Library()


def _auto_prefill(request) -> tuple[str, str]:
    """Best-effort context label + suggested prefill from `request.path`."""
    path = (request.path or '').rstrip('/')
    if not path or path == '/dashboard':
        return ('the dashboard', 'show me a snapshot of the store right now')
    m = re.match(r'/dashboard/orders/([\w-]+)', path)
    if m:
        return (f'order #{m.group(1)}', f'investigate order #{m.group(1)} and tell me what stands out')
    m = re.match(r'/dashboard/products/?$', path)
    if m:
        return ('the products list', 'show me low-stock products and which ones to refresh copy for')
    m = re.match(r'/dashboard/customers/?$', path)
    if m:
        return ('customers', 'who are my top 5 customers by lifetime spend?')
    if path.startswith('/dashboard/analytics'):
        return ('analytics', 'summarise this week vs last week — biggest movers')
    if path.startswith('/dashboard/seo'):
        return ('SEO', 'audit my products and tell me the worst 5')
    if path.startswith('/dashboard/crm'):
        return ('CRM', 'what follow-up tasks do I have due today?')
    if path.startswith('/dashboard/affiliates') or path.startswith('/dashboard/apps/affiliates'):
        return ('affiliates', 'which affiliates are pending payout right now?')
    if path.startswith('/dashboard/agents') or path.startswith('/dashboard/apps/agent_core'):
        return ('agent runs', 'show me agent runs that failed in the last 24h')
    return (path, f'help me with {path}')


@register.simple_tag(takes_context=True)
def morph_ask(context, context_label: str = '', prefill: str = '', label: str = ''):
    request = context.get('request')
    if request is None:
        return ''
    if not context_label or not prefill:
        auto_label, auto_prefill = _auto_prefill(request)
        context_label = context_label or auto_label
        prefill = prefill or auto_prefill
    label = label or 'Ask Linda'

    # The button posts a custom event the floating widget listens for.
    return mark_safe(
        '<button type="button" class="morph-ask-btn" '
        f'data-prefill="{prefill}" data-label="{context_label}" '
        'onclick="window.dispatchEvent(new CustomEvent(\'morph:ask\', '
        '{detail:{prefill: this.dataset.prefill, label: this.dataset.label}}))" '
        'style="display:inline-flex;align-items:center;gap:.4rem;'
        'padding:.35rem .7rem;border:1px solid var(--border);border-radius:999px;'
        'background:var(--surface-2);font-size:.78rem;font-weight:500;cursor:pointer;'
        'color:var(--text);">'
        '<span style="font-size:.85rem;">✦</span> '
        f'{label} <span style="opacity:.6;">about {context_label}</span>'
        '</button>'
    )
