from django.urls import path

from plugins.installed.cjdropshipping import views

app_name = 'cjdropshipping_webhook'

urlpatterns = [
    path('webhook/', views.webhook_view, name='webhook'),
]
