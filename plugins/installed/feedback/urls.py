"""Feedback routes.

**Both routes must be four segments deep.** admin_dashboard's app-discovery
router owns `dashboard/apps/<str:plugin>/<str:slug>/`, and it is registered
first, so any three-segment sibling here is swallowed by that converter and
answers 404: `dashboard/apps/feedback/submit/` resolved as
(plugin=feedback, slug=submit), found no DashboardPage by that slug, and 404'd
while the four-segment detail route resolved fine. Nesting under `tickets/`
clears the converter and keeps the paths readable.

Literal before converter, per the same rule.
"""

from __future__ import annotations

from django.urls import path

from . import views

urlpatterns = [
    path('tickets/submit/', views.submit, name='submit'),
    path('tickets/<uuid:pk>/', views.ticket_detail, name='detail'),
]
