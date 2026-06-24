"""ACP checkout-session routes — mounted at /acp/ via register_urls."""

from __future__ import annotations

from django.urls import path

from plugins.installed.agentic_checkout import feed, views

app_name = 'agentic_checkout'

urlpatterns = [
    path('checkout_sessions', views.create_checkout_session, name='create'),
    path('checkout_sessions/<str:session_id>', views.checkout_session_detail, name='detail'),
    path(
        'checkout_sessions/<str:session_id>/cancel',
        views.cancel_checkout_session,
        name='cancel',
    ),
    path(
        'checkout_sessions/<str:session_id>/complete',
        views.complete_checkout_session,
        name='complete',
    ),
    path('feed.json', feed.product_feed, name='feed'),
]
