from django.urls import path

from plugins.installed.tracking import views

app_name = 'tracking'

urlpatterns = [
    path('', views.overview, name='overview'),
    path('settings/', views.settings_page, name='settings'),
    path('events/', views.event_log, name='event_log'),
    path('events/<uuid:event_id>/', views.event_detail, name='event_detail'),
    path('test/', views.test_purchase, name='test_purchase'),
    # Per-event diagnostic. Accepts ?format=json for AJAX dashboards.
    path('test/<str:event_name>/', views.test_event, name='test_event'),
    # Validates measurement_id + api_secret against the GA4 debug
    # endpoint. JSON-only response.
    path('connection-check/', views.connection_check, name='connection_check'),
    path('container.json', views.gtm_container_export, name='gtm_container_export'),
]
