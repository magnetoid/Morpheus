"""Feature-adoption dashboard (admin-only)."""

from __future__ import annotations

from django.http import HttpRequest, HttpResponse


def adoption_dashboard(request: HttpRequest) -> HttpResponse:
    """Adoption matrix + install-health, staff-gated."""
    from morpheus.plugin.views import render, staff_required  # noqa: PLC0415

    @staff_required
    def _inner(req: HttpRequest) -> HttpResponse:
        from plugins.installed.feature_adoption.tracking import (  # noqa: PLC0415
            adoption_matrix,
            install_health,
        )

        data = adoption_matrix()
        return render(
            req,
            'feature_adoption/dashboard.html',
            {
                'rows': data['rows'],
                'never_used': data['never_used'],
                'health': install_health(),
                'active_nav': 'apps',
            },
        )

    return _inner(request)
