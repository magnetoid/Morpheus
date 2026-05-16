from django.urls import path

from core.errors import views

app_name = 'errors'

urlpatterns = [
    # POST endpoint for browser-side JS error capture.
    path('api/errors/client/', views.client_error_ingest, name='client_ingest'),
    # Dashboard surface.
    path('dashboard/errors/', views.errors_list, name='list'),
    path('dashboard/errors/<str:fingerprint>/', views.errors_detail, name='detail'),
]
