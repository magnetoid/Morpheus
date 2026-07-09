from django.urls import path

from plugins.installed.live_commerce import views_storefront as v

app_name = 'live_commerce_storefront'
urlpatterns = [
    path('live/', v.live_index, name='index'),
    path('live/<slug:slug>/', v.live_event, name='event'),
]
