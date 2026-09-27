import logging

from django.conf import settings
from django.core.mail.backends.console import EmailBackend as ConsoleBackend
from django.core.mail.backends.smtp import EmailBackend as SmtpBackend

from core.models import StoreSettings

logger = logging.getLogger('morpheus.email')


def smtp_configured() -> bool:
    """Whether outbound email has a real transport (StoreSettings or env).

    Without one, MorpheusEmailBackend prints every message to the log instead
    of sending it — sign-in codes and order emails included.
    """
    if getattr(settings, 'EMAIL_HOST', ''):
        return True
    try:
        row = StoreSettings.objects.first()
    except Exception:  # noqa: BLE001 — no table yet (fresh install)
        return False
    return bool(row and row.smtp_host)


class MorpheusEmailBackend:
    """Composite email backend.

    Reads SMTP config from ``StoreSettings`` (admin-editable singleton), falling
    back to ``EMAIL_*`` environment variables. When neither path resolves a host
    we drop to the console backend so dev work and unconfigured installs see
    every outbound message in stdout instead of silently failing or 500-ing.
    """

    def __init__(self, fail_silently=False, **kwargs):
        host = getattr(settings, 'EMAIL_HOST', '')
        port = getattr(settings, 'EMAIL_PORT', 587)
        username = getattr(settings, 'EMAIL_HOST_USER', '')
        password = getattr(settings, 'EMAIL_HOST_PASSWORD', '')
        use_tls = getattr(settings, 'EMAIL_USE_TLS', True)
        try:
            store_settings = StoreSettings.objects.first()
            if store_settings and store_settings.smtp_host:
                host = store_settings.smtp_host
                port = store_settings.smtp_port
                username = store_settings.smtp_user
                password = store_settings.smtp_password
            if store_settings and store_settings.default_from_email:
                settings.DEFAULT_FROM_EMAIL = store_settings.default_from_email
        except Exception:  # noqa: BLE001, S110
            pass

        if host:
            self._backend = SmtpBackend(
                host=host,
                port=port,
                username=username,
                password=password,
                use_tls=use_tls,
                fail_silently=fail_silently,
                **kwargs,
            )
        else:
            # No SMTP configured — log every outbound email to stdout so
            # devs and merchants can see what was attempted before they
            # wire a real provider. In production that silently meant no
            # email was ever delivered, so say so where someone will see it.
            if not settings.DEBUG:
                logger.warning(
                    'email: no SMTP host is configured (Settings → Notifications, or '
                    'EMAIL_HOST) — this message is written to the log, not delivered'
                )
            self._backend = ConsoleBackend(fail_silently=fail_silently, **kwargs)

    def __getattr__(self, name):
        return getattr(self._backend, name)
