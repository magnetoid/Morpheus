from django.urls import path

from plugins.installed.promotions import views

app_name = 'promotions'

urlpatterns = [
    path('', views.promotions_index, name='index'),
    path('new/', views.promotion_new, name='new'),
    path('<uuid:promotion_id>/', views.promotion_edit, name='edit'),
    path('<uuid:promotion_id>/toggle/', views.promotion_toggle, name='toggle'),
]
