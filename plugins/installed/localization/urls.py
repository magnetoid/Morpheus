from django.urls import path

from plugins.installed.localization import views

app_name = 'localization'

urlpatterns = [
    path('translations/', views.translations_index, name='translations'),
    path('languages/', views.languages_index, name='languages'),
]
