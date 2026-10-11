from django.urls import path

from core.errors import views

app_name = 'errors'

urlpatterns = [
    # POST endpoint for browser-side JS error capture.
    path('api/errors/client/', views.client_error_ingest, name='client_ingest'),
    # Dashboard surface. Literal routes before `<str:fingerprint>/`, which would
    # otherwise take "report" and "detailed" as fingerprints.
    path('dashboard/errors/', views.errors_list, name='list'),
    path('dashboard/errors/report/', views.errors_report, name='report'),
    path('dashboard/errors/detailed/', views.errors_detailed, name='detailed'),
    path('dashboard/errors/<str:fingerprint>/', views.errors_detail, name='detail'),
    path('dashboard/errors/<str:fingerprint>/resolve/', views.errors_resolve, name='resolve'),
]
