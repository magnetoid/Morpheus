from django.urls import path

from . import views

app_name = 'lumina'

urlpatterns = [
    path('create/', views.landing, name='landing'),
]
