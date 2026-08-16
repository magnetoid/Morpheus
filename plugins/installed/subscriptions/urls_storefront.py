"""Public storefront routes — the membership / plans page + subscribe."""

from __future__ import annotations

from django.urls import path

from plugins.installed.subscriptions import views_storefront as v

app_name = 'subscriptions_storefront'

urlpatterns = [
    path('membership/', v.membership_view, name='membership'),
    # Literal before converter (CLAUDE.md): `subscribe/` is exact, so the
    # uuid routes below cannot swallow it.
    path('membership/subscribe/', v.subscribe_view, name='subscribe'),
    path('membership/subscribe/<uuid:plan_id>/', v.subscribe_start_view, name='subscribe_start'),
    path(
        'membership/subscribe/<uuid:plan_id>/confirm/',
        v.subscribe_confirm_view,
        name='subscribe_confirm',
    ),
]
