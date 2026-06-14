"""Dashboard routes — mounted under /dashboard/stories/."""

from __future__ import annotations

from django.urls import path

from plugins.installed.product_stories import dashboard

app_name = 'product_stories_dash'

urlpatterns = [
    path('', dashboard.stories_index, name='index'),
    path('<slug:slug>/', dashboard.stories_product, name='product'),
]
