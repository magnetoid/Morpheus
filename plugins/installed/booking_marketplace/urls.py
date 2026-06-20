from django.urls import path

from plugins.installed.booking_marketplace import views

app_name = 'booking_marketplace'

urlpatterns = [
    path('bookings/', views.services_list, name='list'),
    path('bookings/<slug:slug>/', views.service_detail, name='detail'),
]
