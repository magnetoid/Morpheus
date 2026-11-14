import logging
from email.errors import HeaderParseError
from email.headerregistry import Address
from email.utils import parseaddr
from urllib.parse import urlsplit

from django.conf import settings
from django.core.mail.backends.console import EmailBackend as ConsoleBackend
from django.core.mail.backends.smtp import EmailBackend as SmtpBackend

from core.models import StoreSettings
from core.utils.site import site_base_url

logger = logging.getLogger('morpheus.email')


def sender_name(row=None) -> str:
    """The name a customer sees beside the store's address: the store's own.

    A bare address is shown by its local part, so every email read "hello".
    The store name (Settings → General), else ``STORE_NAME``, skipping the
    "Morpheus Store" default (it names the business after the engine), else
    the site's host. Whitespace is collapsed, so a line break never reaches
    a header.
    """
    default = StoreSettings._meta.get_field('store_name').default
    for value in (getattr(row, 'store_name', ''), getattr(settings, 'STORE_NAME', '')):
        name = ' '.join(str(value or '').split())
        if name and name != default:
            return name
    host = (urlsplit(site_base_url()).hostname or '').lstrip('.')
    return '' if host == '*' else host


def with_store_name(address: str, name: str) -> str:
    """``address`` with ``name`` beside it, unless it already has a name."""
    display, addr = parseaddr(address or '')
    if display or not addr or not name:
        return address
    try:
        return str(Address(display_name=name, addr_spec=addr))
    except (ValueError, IndexError, HeaderParseError):
        return address


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

    The merchant's sender (``StoreSettings.default_from_email``) replaces the
    deployment's ``DEFAULT_FROM_EMAIL`` at send time, in ``send_messages``,
    with the store's name beside it (:func:`sender_name`).
    """

    def __init__(self, fail_silently=False, **kwargs):
        host = getattr(settings, 'EMAIL_HOST', '')
        port = getattr(settings, 'EMAIL_PORT', 587)
        username = getattr(settings, 'EMAIL_HOST_USER', '')
        password = getattr(settings, 'EMAIL_HOST_PASSWORD', '')
        use_tls = getattr(settings, 'EMAIL_USE_TLS', True)
        self._sender = ''
        store_settings = None
        try:
            store_settings = StoreSettings.objects.first()
            if store_settings and store_settings.smtp_host:
                host = store_settings.smtp_host
                port = store_settings.smtp_port
                username = store_settings.smtp_user
                password = store_settings.smtp_password
            if store_settings and store_settings.default_from_email:
                self._sender = store_settings.default_from_email
        except Exception:  # noqa: BLE001, S110
            pass
        self._name = sender_name(store_settings)

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

    def send_messages(self, email_messages):
        # Callers build messages from DEFAULT_FROM_EMAIL, usually before any
        # backend exists in the process (async mail is built in the web
        # process and sent by the worker), so the merchant's sender is applied
        # here, where every message passes, with the store's name beside it.
        # An explicit other sender is kept as written.
        fallback = parseaddr(settings.DEFAULT_FROM_EMAIL)[1]
        own = parseaddr(self._sender)[1]
        sender = with_store_name(self._sender or settings.DEFAULT_FROM_EMAIL, self._name)
        for message in email_messages:
            name, addr = parseaddr(message.from_email or '')
            if addr == fallback or (addr == own and not name):
                message.from_email = sender
        return self._backend.send_messages(email_messages)

    def __getattr__(self, name):
        return getattr(self._backend, name)
