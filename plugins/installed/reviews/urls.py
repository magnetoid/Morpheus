from django.urls import path

from plugins.installed.reviews import views

app_name = 'reviews'

urlpatterns = [
    path('add/<uuid:product_id>/', views.add_review, name='add'),
]
