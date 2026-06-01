from django.urls import path

from . import views

app_name = 'bookstore_3d'

urlpatterns = [
    path('walkthrough/', views.walkthrough, name='walkthrough'),
]
