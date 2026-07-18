"""Storefront routes owned by eco_impact (mounted at site root by
``register_urls``). Present only while the plugin is enabled — disabling it
404s every route below (modular-os disable test)."""

from __future__ import annotations

from django.urls import path

from plugins.installed.eco_impact import views

app_name = 'eco_impact'

urlpatterns = [
    path('save-the-planet/', views.save_the_planet, name='save_the_planet'),
    path('checkout/plant-a-tree/apply/', views.apply_optin, name='apply_optin'),
    path('checkout/plant-a-tree/remove/', views.remove_optin, name='remove_optin'),
]
