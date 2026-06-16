from django.urls import path

from plugins.installed.pinterest_commerce import views

app_name = 'pinterest_commerce'

urlpatterns = [
    path('feeds/pinterest-catalog.xml', views.pinterest_catalog_feed, name='feed'),
]
