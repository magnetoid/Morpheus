"""eco_impact views — checkout opt-in endpoints, the public impact page, and
the dashboard summary. All storefront routes work for guests and members."""

from __future__ import annotations

import logging

from django.shortcuts import redirect, render

from plugins.installed.eco_impact import footprint, services

logger = logging.getLogger('morpheus.eco_impact')


def _back(request, default='/cart/'):
    """The referring page without its query (theme has no messages framework)."""
    ref = request.META.get('HTTP_REFERER', default) or default
    return ref.split('?')[0]


def apply_optin(request):
    """POST /checkout/plant-a-tree/apply/ — opt the current cart into the offset."""
    if request.method != 'POST':
        return redirect('/cart/')
    try:
        services.set_optin(request, True)
    except Exception as exc:  # noqa: BLE001
        logger.warning('eco apply_optin failed: %s', exc, exc_info=True)
    return redirect(_back(request))


def remove_optin(request):
    """POST /checkout/plant-a-tree/remove/ — drop the offset from the cart."""
    if request.method != 'POST':
        return redirect('/cart/')
    try:
        services.set_optin(request, False)
    except Exception as exc:  # noqa: BLE001
        logger.warning('eco remove_optin failed: %s', exc, exc_info=True)
    return redirect(_back(request))


def save_the_planet(request):
    """GET /save-the-planet/ — public impact page: store totals + methodology."""
    totals = services.store_totals()
    d = footprint.DEFAULTS
    return render(
        request,
        'eco_impact/save_the_planet.html',
        {
            'totals': totals,
            'tree_price': services.surcharge_amount(),
            'kg_co2_per_tree': services.kg_co2_per_tree(),
            'wood_factor': d['wood_factor'],
            'co2_per_kg_paper': d['co2_per_kg_paper'],
        },
    )


def dashboard(request):
    """GET /dashboard/eco-impact/ — merchant summary of the tree fund."""
    from plugins.installed.eco_impact.models import TreePledge

    pledges = list(TreePledge.objects.all()[:100])
    return render(
        request,
        'eco_impact/dashboard.html',
        {
            'totals': services.store_totals(),
            'pledges': pledges,
            'tree_price': services.surcharge_amount(),
            'active_nav': 'marketing',
        },
    )
