from django.urls import path

from plugins.installed.cjdropshipping import views

app_name = 'cjdropshipping'

urlpatterns = [
    path('connection/test/', views.test_connection_view, name='test_connection'),
    path('webhooks/register/', views.register_webhooks_view, name='register_webhooks'),
    path('products/import/', views.import_product_view, name='import_product'),
    path('orders/sync/', views.sync_view, name='sync'),
    path('orders/<str:order_number>/send/', views.send_order_view, name='send_order'),
    path('orders/<str:order_number>/pay/', views.pay_order_view, name='pay_order'),
]
