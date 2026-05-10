from django.urls import path

from plugins.installed.reviews import dashboard

app_name = 'reviews_dashboard'

urlpatterns = [
    path('', dashboard.reviews_list, name='list'),
    path('<uuid:review_id>/action/', dashboard.review_action, name='action'),
    path('<uuid:review_id>/respond/', dashboard.review_respond, name='respond'),
]
