from django.apps import AppConfig


class PaymentsConfig(AppConfig):
    name = 'plugins.installed.payments'
    label = 'payments'
    verbose_name = 'Payments'

    def ready(self):
        from plugins.installed.payments.plugin import PaymentsPlugin
        from plugins.registry import plugin_registry

        if 'payments' not in plugin_registry._classes:
            plugin_registry._classes['payments'] = PaymentsPlugin


default_app_config = 'plugins.installed.payments.apps.PaymentsConfig'
