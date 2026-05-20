from django.urls import path

from plugins.installed.store_bootstrap import views

app_name = 'store_bootstrap'

urlpatterns = [
    path('start/', views.bootstrap_view, name='start'),
]
