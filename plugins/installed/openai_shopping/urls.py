from django.urls import path

from plugins.installed.openai_shopping import views

app_name = 'openai_shopping'

urlpatterns = [
    path('feeds/openai-products.jsonl', views.feed_jsonl, name='feed'),
]
