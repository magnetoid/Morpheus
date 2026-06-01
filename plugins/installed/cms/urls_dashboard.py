"""CMS dashboard sub-routes (mounted under /dashboard/cms/).

Parameterised page CRUD the DashboardPage router can't express (it maps one
slug → one view). The Pages LIST stays at /dashboard/apps/cms/pages/ via
``contribute_dashboard_pages``; these are the new/edit/duplicate/delete actions
it links to. Every target view is ``@staff_member_required``. Registered in
``cms/plugin.py:ready()`` — disable the plugin and these routes disappear.
"""

from __future__ import annotations

from django.urls import path

from plugins.installed.cms import dashboard

app_name = 'cms_dashboard'

urlpatterns = [
    path('pages/new/', dashboard.page_edit, {'page_id': None}, name='page_new'),
    path('pages/<uuid:page_id>/edit/', dashboard.page_edit, name='page_edit'),
    path('pages/<uuid:page_id>/duplicate/', dashboard.page_duplicate, name='page_duplicate'),
    path('pages/<uuid:page_id>/delete/', dashboard.page_delete, name='page_delete'),
]
