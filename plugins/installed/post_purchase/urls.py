from django.urls import path

from plugins.installed.post_purchase import views

app_name = 'post_purchase'

urlpatterns = [
    path('nps/<str:token>/', views.nps_form, name='nps_form'),
    path('nps/thanks/', views.nps_thanks, name='nps_thanks'),
]
