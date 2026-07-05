from django.urls import path

from plugins.installed.analytics import views

app_name = 'analytics_api'

urlpatterns = [
    path('analytics/track/', views.track_beacon, name='track'),
    path('analytics/realtime.json', views.realtime_json, name='realtime_json'),
    path('analytics/custom-events/', views.custom_events_config, name='custom_events'),
]
