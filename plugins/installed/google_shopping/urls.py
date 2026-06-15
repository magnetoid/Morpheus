from django.urls import path

from plugins.installed.google_shopping import views

app_name = 'google_shopping'

urlpatterns = [
    path('feeds/google-merchant.xml', views.google_merchant_feed, name='feed'),
]
