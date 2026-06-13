from __future__ import annotations

from django.urls import path

from plugins.installed.affiliates import embed_views, views

app_name = 'affiliates'

urlpatterns = [
    path('r/<str:code>', views.affiliate_redirect, name='redirect'),
    # Customer self-service flow
    path('affiliates/apply/', views.apply, name='apply'),
    path('affiliates/me/', views.dashboard, name='dashboard'),
    path('affiliates/me/links/', views.links, name='links'),
    path('affiliates/me/creatives/', views.creatives, name='creatives'),
    path('affiliates/me/links/new/', views.create_link, name='create_link'),
    path('affiliates/me/links/<uuid:link_id>/edit/', views.edit_link, name='edit_link'),
    path('affiliates/me/conversions/', views.conversions, name='conversions'),
    path('affiliates/me/analytics/', views.analytics, name='analytics'),
    path('affiliates/me/coupon/', views.coupon, name='coupon'),
    path('affiliates/me/payouts/', views.payouts, name='payouts'),
    path('affiliates/me/leaderboard/', views.leaderboard, name='leaderboard'),
    path('affiliates/me/settings/', views.settings, name='settings'),
    # Embeddable widgets — affiliate-owned management.
    path('affiliates/me/widgets/', views.widgets, name='widgets'),
    path('affiliates/me/widgets/<uuid:widget_id>/edit/', views.edit_widget, name='edit_widget'),
    # ── PUBLIC, cross-origin embed surfaces (anonymous, key-gated) ──
    # iframe document — framable anywhere (per-response framing relaxation).
    path('affiliates/embed/<str:key>/', embed_views.embed_iframe, name='embed_iframe'),
    # JS snippet (CORS) — injects cards into a target div on an external site.
    path('affiliates/embed/<str:key>.js', embed_views.embed_js, name='embed_js'),
    # JSON data (CORS) — public product data + ref links, consumed by the JS.
    path('api/affiliates/widget/<str:key>.json', embed_views.widget_json, name='widget_json'),
]
