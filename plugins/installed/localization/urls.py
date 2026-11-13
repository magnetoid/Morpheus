from django.urls import path

from plugins.installed.localization import views

app_name = 'localization'

# The list itself is the Translations dashboard page (`app.py`), at
# /dashboard/apps/localization/translations/.
urlpatterns = [
    path(
        'translations/<str:kind>/<str:pk>/<str:language>/',
        views.translation_edit,
        name='translation_edit',
    ),
]
