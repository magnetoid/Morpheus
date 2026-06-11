"""Assistant URL routes — mounted at `/dashboard/assistant/` in the project URLconf."""

from __future__ import annotations

from django.urls import path

from core.assistant import views

app_name = 'assistant'

urlpatterns = [
    path('', views.assistant_page, name='page'),
    path('invoke/', views.assistant_invoke, name='invoke'),
    path('stream/', views.assistant_stream, name='stream'),
    path('history/', views.assistant_history, name='history'),
]
