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
        # Refresh reads fresh signals: clear the snapshot cache so the forced
        # analysis (and the page's subsequent GET) sees current data.
        signals.invalidate_signals_cache()
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

    if request.method == 'POST' and request.POST.get('action') == 'refresh_briefing':
        # The long-form briefing is a heavier LLM call than the structured
        # analysis, so it has its own button. Generation lives in the plugin.
        from plugins.installed.morpheus_brain.services import generate_briefing

        signals.invalidate_signals_cache()
        result = generate_briefing()
        if result.get('configured') is False:
            messages.warning(request, result.get('message', 'No AI provider configured.'))
        elif result.get('error'):
            messages.error(request, f'Briefing failed: {result["error"]}')
        else:
            messages.success(request, 'Advisory briefing regenerated.')
        return redirect(f'{request.path}#advisory')

    from plugins.installed.morpheus_brain.models import BrainBriefing

    data = signals.gather_all()
    analysis = analyst.cached_analysis()
    briefing = BrainBriefing.objects.order_by('-generated_at').first()
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
            'briefing': briefing,
        },
    )
