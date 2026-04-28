from django.urls import path

from plugins.installed.draft_orders import views

app_name = 'draft_orders'

urlpatterns = [
    path('', views.index, name='index'),
    path('<str:number>/', views.detail, name='detail'),
    path('<str:number>/convert/', views.convert, name='convert'),
    path('<str:number>/cancel/', views.cancel, name='cancel'),
    path('<str:number>/lines/add/', views.line_add, name='line_add'),
    path('<str:number>/lines/<uuid:line_id>/delete/', views.line_delete, name='line_delete'),
]
