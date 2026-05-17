from django.urls import path

from plugins.installed.tracking import views

app_name = 'tracking'

urlpatterns = [
    path('', views.overview, name='overview'),
    path('settings/', views.settings_page, name='settings'),
    path('events/', views.event_log, name='event_log'),
    path('events/<uuid:event_id>/', views.event_detail, name='event_detail'),
    path('test/', views.test_purchase, name='test_purchase'),
    path('container.json', views.gtm_container_export, name='gtm_container_export'),
]
