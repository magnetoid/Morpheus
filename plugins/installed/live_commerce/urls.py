from django.urls import path

from plugins.installed.live_commerce import views

app_name = 'live_commerce'
urlpatterns = [
    path('', views.index, name='index'),
    path('new/', views.edit_event, {'event_id': None}, name='event_new'),
    path('<uuid:event_id>/', views.edit_event, name='event_edit'),
    path('<uuid:event_id>/delete/', views.delete_event, name='event_delete'),
    path('<uuid:event_id>/status/', views.set_status, name='event_status'),
]
