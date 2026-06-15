from django.urls import path

from plugins.installed.meta_commerce import views

app_name = 'meta_commerce'

urlpatterns = [
    path('feeds/meta-catalog.xml', views.meta_catalog_feed, name='feed'),
]
