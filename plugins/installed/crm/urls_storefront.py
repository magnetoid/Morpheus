"""Public support-chat endpoints (mounted at root): /support/chat/send|poll/."""

from __future__ import annotations

from django.urls import path

from plugins.installed.crm import chat_views

app_name = 'crm_support'

urlpatterns = [
    path('support/chat/send/', chat_views.chat_send, name='chat_send'),
    path('support/chat/poll/', chat_views.chat_poll, name='chat_poll'),
]
