"""demo_data dashboard view — rendered as the plugin's settings page."""

from __future__ import annotations

from core.authz import require_capability
from morpheus.app.views import messages, render, staff_member_required


@staff_member_required
@require_capability('system.write')
def demo_data_index(request):
    """Settings page for the demo_data plugin.

    Mounted at `/dashboard/apps/demo_data/settings/` by the unified
    settings hub. Lets the merchant generate sample data on demand —
    products are themed by the active storefront theme.
    """
    from plugins.installed.demo_data.services import (
        SeedSummary,
        _detect_topic,
        seed_all,
        seed_random_products,
    )

    last_summary: SeedSummary | None = None
    if request.method == 'POST':
        action = request.POST.get('action', 'random')
        try:
            if action == 'full':
                last_summary = seed_all(wipe=bool(request.POST.get('wipe')))
                messages.success(request, f'Full demo seeded: {last_summary.counts}')
            elif action == 'wipe_random':
                last_summary = seed_random_products(count=0, wipe_random=True)
                messages.success(request, f'Random demo wiped: {last_summary.counts}')
            else:  # random
                count = int(request.POST.get('count', 30) or 30)
                topic = (request.POST.get('topic') or '').strip()
                last_summary = seed_random_products(count=count, topic=topic)
                messages.success(request, f'Generated random products: {last_summary.counts}')
        except Exception as e:  # noqa: BLE001
            messages.error(request, f'Seed failed: {e}')

    return render(
        request,
        'demo_data/settings.html',
        {
            'detected_topic': _detect_topic(),
            'last_summary': last_summary,
            'active_nav': 'settings',
        },
    )
