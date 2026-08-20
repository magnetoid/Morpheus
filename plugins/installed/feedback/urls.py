"""Feedback routes.

Nested under `tickets/` for readability — since v0.53.0 plugin mounts resolve
BEFORE the shell's app-discovery router (most-specific prefix first), so the
nesting is no longer load-bearing; these are simply this app's public paths
(the JS and tests point at them). Literal before converter.
"""

from __future__ import annotations

from django.urls import path

from . import views

urlpatterns = [
    path('tickets/submit/', views.submit, name='submit'),
    path('tickets/<uuid:pk>/', views.ticket_detail, name='detail'),
]
