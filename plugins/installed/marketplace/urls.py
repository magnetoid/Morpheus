from __future__ import annotations

from django.urls import path

from plugins.installed.marketplace import views

app_name = 'marketplace'

urlpatterns = [
    # Storefront vendor self-service flow.
    path('vendor/apply/', views.apply, name='apply'),
    path('vendor/me/', views.dashboard, name='dashboard'),
    path('vendor/me/products/', views.vendor_products, name='vendor_products'),
    path('vendor/me/products/<uuid:product_id>/', views.vendor_product_edit, name='vendor_product_edit'),
]
