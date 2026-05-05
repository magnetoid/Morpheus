from django.urls import path

from plugins.installed.crm import views

app_name = 'crm'

urlpatterns = [
    path('', views.crm_home, name='home'),
    path('leads/', views.leads_list, name='leads'),
    path('pipeline/', views.pipeline_board, name='pipeline'),
    path('tasks/', views.tasks_list, name='tasks'),
    path('inbox/', views.inbox_list, name='inbox'),
    path('inbox/compose/', views.inbox_compose, name='inbox_compose'),
    path('inbox/accounts/', views.inbox_accounts, name='inbox_accounts'),
    path('inbox/<uuid:message_id>/', views.inbox_message, name='inbox_message'),
]
