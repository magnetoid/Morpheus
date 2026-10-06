from django.urls import path

from plugins.installed.zendrop import views

app_name = 'zendrop'

urlpatterns = [
    path('connection/test/', views.test_connection_view, name='test_connection'),
    path('orders/<str:order_number>/placed/', views.mark_placed_view, name='mark_placed'),
    path('orders/<str:order_number>/ship/', views.ship_order_view, name='ship_order'),
    path('import/tracking/', views.import_tracking_view, name='import_tracking'),
]
