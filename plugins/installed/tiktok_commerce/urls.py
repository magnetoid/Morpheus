from django.urls import path

from plugins.installed.tiktok_commerce import views

app_name = 'tiktok_commerce'

urlpatterns = [
    path('feeds/tiktok-catalog.xml', views.tiktok_catalog_feed, name='feed'),
]
