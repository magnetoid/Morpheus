"""One-prompt store bootstrap.

GET  /dashboard/start/  → the wizard form (single textarea + sample prompts).
POST /dashboard/start/  → run the bootstrap synchronously (~10-30 s LLM call),
                          render the success state with a summary.

This is the AI-first onboarding promise: empty dashboard → describe
your store in one sentence → populated catalogue + brand voice + ready
storefront. The LLM call is synchronous; we accept the 10-30 s wait
because that's the demo (anyone watching sees the magic finish).
"""
from __future__ import annotations

import logging

from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

logger = logging.getLogger('morpheus.admin_dashboard.bootstrap')


_SAMPLE_PROMPTS = [
    "An independent bookshop specialising in queer literary fiction and translated essays.",
    "A modern Japanese tea shop selling single-estate matcha, sencha, and hand-thrown ceramics.",
    "A direct-to-consumer brand of small-batch, low-acid cold-brew coffee.",
    "A studio shop for hand-bound notebooks, archival pens, and printable stationery sets.",
]


@staff_member_required
@require_http_methods(['GET', 'POST'])
def bootstrap_view(request):
    if request.method == 'GET':
        return render(request, 'admin_dashboard/bootstrap.html', {
            'sample_prompts': _SAMPLE_PROMPTS,
            'active_nav': 'home',
        })

    prompt = (request.POST.get('prompt') or '').strip()
    if not prompt:
        return render(request, 'admin_dashboard/bootstrap.html', {
            'sample_prompts': _SAMPLE_PROMPTS,
            'error': 'Tell me what kind of store you want to build.',
            'active_nav': 'home',
        })

    from plugins.installed.admin_dashboard.services.bootstrap import (
        bootstrap_store_from_prompt,
    )
    result = bootstrap_store_from_prompt(prompt)

    return render(request, 'admin_dashboard/bootstrap.html', {
        'sample_prompts': _SAMPLE_PROMPTS,
        'result': result,
        'prompt': prompt,
        'active_nav': 'home',
    })
