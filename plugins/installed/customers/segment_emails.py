"""Answer CUSTOMER_SEGMENT_EMAILS: the emails of the customers in one RFM segment."""

from __future__ import annotations


def on_segment_emails(value, segment='', **kwargs) -> set[str]:
    """Lower-cased emails of the customers whose segment is ``segment``."""
    from plugins.installed.customers.models import CustomerSegment

    emails = CustomerSegment.objects.filter(segment=segment).values_list(
        'customer__email', flat=True
    )
    return {e.strip().lower() for e in emails if e and e.strip()}
