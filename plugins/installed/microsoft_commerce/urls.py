from django.urls import path

from plugins.installed.microsoft_commerce import views

app_name = 'microsoft_commerce'

urlpatterns = [
    path('feeds/microsoft-catalog.xml', views.microsoft_catalog_feed, name='feed'),
]
