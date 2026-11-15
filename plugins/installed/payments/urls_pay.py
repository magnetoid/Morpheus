from django.urls import path

from plugins.installed.payments import views_pay

app_name = 'payments_pay'

urlpatterns = [
    path('<str:token>/', views_pay.pay_order, name='pay'),
]
