"""Store-bootstrap views.

GET  /dashboard/apps/store_bootstrap/start/  → wizard form.
POST /dashboard/apps/store_bootstrap/start/  → run the bootstrap
    synchronously (~10-30 s LLM call), render the success state.

The LLM call is synchronous; we accept the 10-30 s wait because that's
the demo (anyone watching sees the magic finish).
"""

from __future__ import annotations

import logging

from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

logger = logging.getLogger('morpheus.store_bootstrap')


_SAMPLE_PROMPTS = [
    'An independent bookshop specialising in queer literary fiction and translated essays.',
    'A modern Japanese tea shop selling single-estate matcha, sencha, and hand-thrown ceramics.',
    'A direct-to-consumer brand of small-batch, low-acid cold-brew coffee.',
    'A studio shop for hand-bound notebooks, archival pens, and printable stationery sets.',
]


@staff_member_required
@require_http_methods(['GET', 'POST'])
def bootstrap_view(request):
    ctx_base = {
        'sample_prompts': _SAMPLE_PROMPTS,
        'active_nav': 'home',
    }
    if request.method == 'GET':
        return render(request, 'store_bootstrap/start.html', ctx_base)

    prompt = (request.POST.get('prompt') or '').strip()
    if not prompt:
        return render(
            request,
            'store_bootstrap/start.html',
            {
                **ctx_base,
                'error': 'Tell me what kind of store you want to build.',
            },
        )

    from plugins.installed.store_bootstrap.services import (
        bootstrap_store_from_prompt,
    )

    result = bootstrap_store_from_prompt(prompt)

    return render(
        request,
        'store_bootstrap/start.html',
        {
            **ctx_base,
            'result': result,
            'prompt': prompt,
        },
    )
