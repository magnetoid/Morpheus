from django.apps import AppConfig


class PaymentsConfig(AppConfig):
    name = 'plugins.installed.payments'
    label = 'payments'
    verbose_name = 'Payments'

    def ready(self):
        from plugins.installed.payments.app import PaymentsPlugin
        from plugins.registry import app_registry

        if 'payments' not in app_registry._classes:
            app_registry._classes['payments'] = PaymentsPlugin


default_app_config = 'plugins.installed.payments.apps.PaymentsConfig'
