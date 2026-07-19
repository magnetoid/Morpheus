"""Public cart-recovery routes — mounted at the site root."""

from __future__ import annotations

from django.urls import path

from plugins.installed.cart_abandonment import views

app_name = 'cart_abandonment'

urlpatterns = [
    path(
        'cart-recovery/unsubscribe/<str:token>/',
        views.unsubscribe_view,
        name='unsubscribe',
    ),
]
