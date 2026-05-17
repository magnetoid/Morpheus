from django.urls import path

from plugins.installed.seo import views

app_name = 'seo_dashboard'

urlpatterns = [
    path('', views.seo_overview, name='overview'),
    path('settings/', views.seo_settings_page, name='settings'),
    path('not-found/', views.not_found_log, name='not_found'),
    path('not-found/<uuid:log_id>/redirect/', views.not_found_create_redirect, name='not_found_redirect'),
    path('audit/', views.audit_page, name='audit'),
    path('keywords/', views.keywords_page, name='keywords'),
    path('bulk-meta/', views.bulk_meta, name='bulk_meta'),
    path('sitemap/', views.sitemap_page, name='sitemap'),
]
