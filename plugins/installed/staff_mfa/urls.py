from django.urls import path

from plugins.installed.staff_mfa import views

app_name = 'staff_mfa'

urlpatterns = [
    path('challenge/', views.challenge, name='challenge'),
]
