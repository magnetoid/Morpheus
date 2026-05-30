"""B2B dashboard sub-routes (mounted under /dashboard/b2b/).

The list view is contributed via `DashboardPage` and ends up at
`/dashboard/apps/b2b/pricelists/`. The drill-in detail view lives here.
"""

from __future__ import annotations

from django.urls import path

from plugins.installed.b2b import dashboard

app_name = 'b2b_dashboard'

urlpatterns = [
    path(
        'pricelists/<uuid:pricelist_id>/',
        dashboard.pricelist_detail,
        name='pricelist_detail',
    ),
]
