from django.urls import path

from plugins.installed.localization import views

app_name = 'localization'

# The list itself is the Translations dashboard page (`app.py`), at
# /dashboard/apps/localization/translations/.
urlpatterns = [
    # Two segments below the app, so the dashboard's apps/<app>/<slug>/ router never takes it.
    path('translations/language-bar/', views.language_bar_save, name='language_bar'),
    path(
        'translations/<str:kind>/<str:pk>/<str:language>/',
        views.translation_edit,
        name='translation_edit',
    ),
]
