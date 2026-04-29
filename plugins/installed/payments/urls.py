from django.urls import path

from plugins.installed.payments import views

app_name = 'payments'

urlpatterns = [
    path('webhooks/stripe/', views.stripe_webhook, name='stripe_webhook'),
]
