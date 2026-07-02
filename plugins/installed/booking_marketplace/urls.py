from django.urls import path

from plugins.installed.booking_marketplace import host, views

app_name = 'booking_marketplace'

urlpatterns = [
    path('bookings/', views.services_list, name='list'),
    path('shop/', views.products_list, name='shop'),
    path('regions/', views.regions_index, name='regions'),
    path('regions/<slug:region>/', views.region_detail, name='region'),
    path('places/', views.places_index, name='places'),
    path('places/<slug:slug>/', views.place_detail, name='place'),
    # Host self-serve — must precede the <slug> detail route below.
    path('bookings/host/', host.host_services, name='host_services'),
    path('bookings/host/new/', host.host_service_form, name='host_new'),
    path('bookings/host/bookings/', host.host_bookings, name='host_bookings'),
    path('bookings/host/enquiries/', host.host_enquiries, name='host_enquiries'),
    path('bookings/host/earnings/', host.host_earnings, name='host_earnings'),
    path('bookings/host/<slug:slug>/edit/', host.host_service_form, name='host_edit'),
    path('bookings/<slug:slug>/review/', views.post_review, name='review'),
    path('bookings/<slug:slug>/', views.service_detail, name='detail'),
]
