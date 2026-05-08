"""URL routes for the passwordless OTP flow.

Mounted at `/auth/otp/` from morph.urls — sits next to allauth's
own `/auth/` namespace without touching it.
"""
from __future__ import annotations

from django.urls import path

from core.auth import views

app_name = 'core_auth'

urlpatterns = [
    path('', views.otp_request, name='otp_request'),
    path('verify/', views.otp_verify, name='otp_verify'),
]
