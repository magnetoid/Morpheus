"""The Help area, mounted at /dashboard/help/ by ReleaseNotesPlugin.ready()."""

from django.urls import path

from plugins.installed.release_notes import help_views

app_name = 'help'

urlpatterns = [
    path('', help_views.help_index, name='index'),
    path('<slug:app>/', help_views.help_app, name='app'),
]
