from django.urls import path

from plugins.installed.seo import views

app_name = 'seo_dashboard'

urlpatterns = [
    path('', views.seo_overview, name='overview'),
    path('settings/', views.seo_settings_page, name='settings'),
    path('not-found/', views.not_found_log, name='not_found'),
    path(
        'not-found/<uuid:log_id>/redirect/',
        views.not_found_create_redirect,
        name='not_found_redirect',
    ),
    path('not-found/<uuid:pk>/dismiss/', views.not_found_dismiss, name='not_found_dismiss'),
    path('redirects/', views.redirects_page, name='redirects'),
    path('rules/', views.index_rules_page, name='index_rules'),
    path('templates/', views.templates_page, name='templates'),
    path('audit/', views.audit_page, name='audit'),
    path('site-audit/run/', views.seo_site_audit_run, name='site_audit_run'),
    path('keywords/', views.keywords_page, name='keywords'),
    path('bulk-meta/', views.bulk_meta, name='bulk_meta'),
    path('sitemap/', views.sitemap_page, name='sitemap'),
    path('inspect/', views.seo_inspector, name='inspector'),
    # Visual structured-data (schema.org) editor.
    path('schema/', views.schema_index, name='schema_index'),
    path('schema/<str:app_label>/<str:model>/<str:pk>/', views.schema_editor, name='schema_editor'),
]
