"""Morpheus Brain surface — thin view over the core engine (core/brain/).

The engine (signal gathering + AI analysis) is core and non-disableable; this
plugin only renders it and exposes the "Refresh analysis" action. GET shows
cached signals + the last AI analysis (no LLM call); POST re-runs the analysis.
"""

from __future__ import annotations

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import redirect, render


@staff_member_required
def brain(request):
    from core.brain import analyst, signals

    if request.method == 'POST' and request.POST.get('action') == 'refresh_analysis':
        result = analyst.get_analysis(force=True)
        if result.get('configured') is False:
            messages.warning(request, result.get('message', 'No AI provider configured.'))
        elif result.get('error'):
            messages.error(request, f'AI analysis failed: {result["error"]}')
        else:
            messages.success(
                request,
                f'Analysis refreshed — {len(result.get("recommendations") or [])} recommendations.',
            )
        return redirect(request.path)

    data = signals.gather_all()
    analysis = analyst.cached_analysis()
    return render(
        request,
        'morpheus_brain/index.html',
        {
            'plugins': data['plugins'],
            'code': data['code'],
            'errors': data['errors'],
            'content': data['content'],
            'storefront': data['storefront'],
            'improvements': data['improvements'],
            'analysis': analysis,
        },
    )
