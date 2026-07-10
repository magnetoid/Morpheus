"""payments' slice of the GDPR erasure hook — drop stored payment methods."""

from __future__ import annotations


def on_customer_anonymise(customer=None, **kwargs):
    """Delete PaymentMethod metadata (the gateway holds the actual card)."""
    from plugins.installed.payments.models import PaymentMethod  # noqa: PLC0415

    PaymentMethod.objects.filter(customer=customer).delete()
