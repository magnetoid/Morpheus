"""The restore screen, mounted at /dashboard/restore/ by ReleaseNotesPlugin.ready()."""

from django.urls import path

from plugins.installed.release_notes import restore_views

app_name = 'restore'

urlpatterns = [
    path('<str:kind>/<str:name>/', restore_views.restore_backup, name='confirm'),
]
