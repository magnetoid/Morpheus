from django.urls import path

from plugins.installed.dsers import views

app_name = 'dsers'

urlpatterns = [
    path('export/orders/', views.export_orders_view, name='export_orders'),
    path('export/products/', views.export_products_view, name='export_products'),
    path('import/tracking/', views.import_tracking_view, name='import_tracking'),
]
