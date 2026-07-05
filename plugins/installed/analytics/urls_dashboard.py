from django.urls import path

from . import views

app_name = 'analytics_dash'
urlpatterns = [
    path('', views.overview, name='overview'),
    path('realtime/', views.realtime, name='realtime'),
    path('funnel/', views.funnel_view, name='funnel'),
    path('cohorts/', views.cohort_view, name='cohorts'),
    path('export/', views.export_data, name='export_data'),
]
