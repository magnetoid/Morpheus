from django.urls import path

from plugins.installed.snapchat_commerce import views

app_name = 'snapchat_commerce'

urlpatterns = [
    path('feeds/snapchat-catalog.xml', views.snapchat_catalog_feed, name='feed'),
]
