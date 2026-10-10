"""The JSONL feed endpoint and the Channels dashboard page."""

from __future__ import annotations

from django.contrib.admin.views.decorators import staff_member_required
from django.core.cache import cache
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from core.authz import require_capability

LAST_PUSH_KEY = 'openai_shopping:last_push'


@require_http_methods(['GET'])
def feed_jsonl(request: HttpRequest) -> HttpResponse:
    """GET /feeds/openai-products.jsonl — one product (or variant) per line.

    Public, like the other channel feeds: every field in it is on the product
    page already. OpenAI fetches it or the merchant uploads it under Feeds.
    """
    from plugins.installed.openai_shopping.feed import build_rows, render_jsonl

    body = render_jsonl(build_rows())
    resp = HttpResponse(body, content_type='application/x-ndjson; charset=utf-8')
    resp['Cache-Control'] = 'public, max-age=900'
    return resp


@staff_member_required
@require_capability('marketing.read')
def dashboard(request: HttpRequest) -> HttpResponse:
    from plugins.installed.openai_shopping.app import FEED_PATH
    from plugins.installed.openai_shopping.feed import config, coverage

    return render(
        request,
        'openai_shopping/dashboard.html',
        {
            'coverage': coverage(),
            'config': config(),
            'feed_url': request.build_absolute_uri(FEED_PATH),
            'last_push': cache.get(LAST_PUSH_KEY) or {},
            'active_nav': 'channels',
            'breadcrumb_trail': [
                {'label': 'Dashboard', 'url': '/dashboard/'},
                {'label': 'Channels', 'url': '/dashboard/channels/'},
                {'label': 'ChatGPT Shopping'},
            ],
        },
    )
