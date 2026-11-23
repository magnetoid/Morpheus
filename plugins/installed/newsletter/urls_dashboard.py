"""Dashboard routes — mounted under /dashboard/newsletter/."""

from __future__ import annotations

from django.urls import path

from plugins.installed.newsletter import dashboard

app_name = 'newsletter_dash'

urlpatterns = [
    path('', dashboard.subscribers_view, name='subscribers'),
    path('popups/', dashboard.popups_view, name='popups'),
    path('popups/<uuid:popup_id>/', dashboard.popup_edit_view, name='popup_edit'),
    path('campaigns/', dashboard.campaigns_view, name='campaigns'),
    path('campaigns/new/', dashboard.campaign_edit_view, name='campaign_new'),
    path('campaigns/<uuid:campaign_id>/', dashboard.campaign_edit_view, name='campaign_edit'),
    path(
        'campaigns/<uuid:campaign_id>/schedule/',
        dashboard.campaign_schedule_view,
        name='campaign_schedule',
    ),
    path(
        'campaigns/<uuid:campaign_id>/cancel/',
        dashboard.campaign_cancel_view,
        name='campaign_cancel',
    ),
    path('campaigns/<uuid:campaign_id>/send/', dashboard.campaign_send_view, name='campaign_send'),
    path('campaigns/<uuid:campaign_id>/test/', dashboard.campaign_test_view, name='campaign_test'),
]
