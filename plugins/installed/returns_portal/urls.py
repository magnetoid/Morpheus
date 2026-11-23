"""The withdrawal function's pages (v0.181.0) and the customer's returns (C4,
v0.188.0), mounted at the site root. Literal paths before converters."""

from __future__ import annotations

from django.urls import path

from plugins.installed.returns_portal import views, views_returns

app_name = 'returns_portal'

urlpatterns = [
    path('withdraw/', views.withdraw, name='withdraw'),
    path('withdraw/confirm/', views.confirm, name='withdraw_confirm'),
    path('withdraw/sent/', views.sent, name='withdraw_sent'),
    path('returns/start/', views_returns.returns_start, name='returns_start'),
    path('account/returns/', views_returns.returns_list, name='returns_list'),
    path('account/returns/<uuid:rma_id>/', views_returns.return_status, name='return_status'),
    path(
        'account/orders/<str:order_number>/return/',
        views_returns.return_form,
        name='return_form',
    ),
]
