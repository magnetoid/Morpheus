from django.urls import path

from plugins.installed.aliexpress import views

app_name = 'aliexpress'

urlpatterns = [
    path('oauth/start/', views.oauth_start_view, name='oauth_start'),
    path('oauth/callback/', views.oauth_callback_view, name='oauth_callback'),
    path('oauth/disconnect/', views.disconnect_view, name='disconnect'),
    path('products/import/', views.import_product_view, name='import_product'),
    path('orders/sync/', views.sync_view, name='sync'),
    path('orders/<str:order_number>/send/', views.send_order_view, name='send_order'),
]
