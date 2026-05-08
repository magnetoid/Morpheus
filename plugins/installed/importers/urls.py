from django.urls import path

from plugins.installed.importers import views

app_name = 'importers'

urlpatterns = [
    path('csv/', views.csv_index, name='csv'),
    path('csv/export/', views.csv_export, name='csv_export'),
    path('shopify/', views.shopify_index, name='shopify'),
]
