"""Dashboard routes for the Bookvault plugin."""
from __future__ import annotations

from django.urls import path

from plugins.installed.bookvault import views

app_name = 'bookvault'

urlpatterns = [
    path('', views.overview, name='overview'),
    path('connect/', views.connect, name='connect'),
    path('resend/<uuid:order_id>/', views.resend_order, name='resend_order'),
    path('bulk-link/', views.bulk_link_products, name='bulk_link'),
    path('webhook/product-link/', views.webhook_product_link, name='webhook_product_link'),
]
