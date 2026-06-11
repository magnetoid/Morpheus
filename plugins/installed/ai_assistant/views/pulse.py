"""Pulse panel actions — refresh + dismiss.

These were dashboard routes in admin_dashboard; they operate purely on
this plugin's MerchantInsight rows, so the plugin owns them (modular-os:
the routes 404 when ai_assistant is disabled, and the home template's
pulse card is {% if pulse %}-guarded so the URL tags never reverse).
"""

from __future__ import annotations

import logging

from morpheus.views import (
    HttpRequest,
    HttpResponse,
    messages,
    redirect,
    staff_member_required,
)

logger = logging.getLogger('morpheus.ai_assistant.pulse')


@staff_member_required
def pulse_refresh(request: HttpRequest) -> HttpResponse:
    """Force a Pulse regeneration on demand. Sync — small enough to not need a task."""
    if request.method != 'POST':
        return redirect('/dashboard/')
    try:
        from plugins.installed.ai_assistant.services.pulse import (  # noqa: PLC0415
            generate_pulse_insights,
        )

        generate_pulse_insights()
    except Exception as e:  # noqa: BLE001
        messages.error(request, f'Pulse refresh failed: {e}')
    else:
        messages.success(request, 'Pulse refreshed.')
    return redirect('/dashboard/')


@staff_member_required
def pulse_dismiss(request: HttpRequest, insight_id: str) -> HttpResponse:
    """Mark a Pulse card read so it falls off the panel."""
    if request.method != 'POST':
        return redirect('/dashboard/')
    try:
        from plugins.installed.ai_assistant.models import MerchantInsight  # noqa: PLC0415

        MerchantInsight.objects.filter(id=insight_id).update(is_read=True)
    except Exception as e:  # noqa: BLE001
        logger.warning('pulse dismiss failed for %s: %s', insight_id, e, exc_info=True)
    return redirect('/dashboard/')
