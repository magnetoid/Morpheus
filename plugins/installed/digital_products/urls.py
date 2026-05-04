from django.urls import path

from plugins.installed.digital_products import views

app_name = 'digital_products'

urlpatterns = [
    path('download/<str:token>/', views.download, name='download'),
]
