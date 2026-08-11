from django.apps import AppConfig


class AdminDashboardConfig(AppConfig):
    name = 'plugins.installed.admin_dashboard'
    label = 'admin_dashboard'
    verbose_name = 'Admin Dashboard'

    def ready(self):
        from plugins.installed.admin_dashboard.app import AdminDashboardPlugin
        from plugins.registry import app_registry

        if 'admin_dashboard' not in app_registry._classes:
            app_registry._classes['admin_dashboard'] = AdminDashboardPlugin


default_app_config = 'plugins.installed.admin_dashboard.apps.AdminDashboardConfig'
