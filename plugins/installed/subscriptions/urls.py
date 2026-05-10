from django.urls import path

from plugins.installed.subscriptions import views

app_name = 'subscriptions'

urlpatterns = [
    path('', views.subscriptions_dashboard, name='dashboard'),
]
