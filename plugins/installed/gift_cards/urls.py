"""Gift cards dashboard URLs."""

from django.urls import path

from plugins.installed.gift_cards import views

app_name = 'gift_cards'

urlpatterns = [
    path('', views.gift_cards_list, name='list'),
    path('new/', views.gift_card_new, name='new'),
    path('<uuid:card_id>/', views.gift_card_detail, name='detail'),
]
