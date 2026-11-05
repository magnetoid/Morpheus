from django.urls import path

from plugins.installed.payments import express, views

app_name = 'payments'

urlpatterns = [
    path('webhooks/stripe/', views.stripe_webhook, name='stripe_webhook'),
    path('webhooks/paypal/', views.paypal_webhook, name='paypal_webhook'),
    path('paypal/return/', views.paypal_return, name='paypal_return'),
    path('paypal/cancel/', views.paypal_cancel, name='paypal_cancel'),
    # Wallet buttons on the cart page (Stripe's Express Checkout Element).
    path('express/quote/', express.express_quote, name='express_quote'),
    path('express/order/', express.express_order, name='express_order'),
]
