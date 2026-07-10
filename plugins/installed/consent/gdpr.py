"""consent's slice of the GDPR export hook — the ConsentLog audit trail."""

from __future__ import annotations


def on_customer_export(value, customer=None, **kwargs):
    from plugins.installed.consent.models import ConsentLog  # noqa: PLC0415

    value['consent.json'] = [
        {
            'necessary': c.necessary,
            'analytics': c.analytics,
            'marketing': c.marketing,
            'functional': c.functional,
            'user_agent': c.user_agent,
            'created_at': c.created_at,
        }
        for c in ConsentLog.objects.filter(customer=customer)
    ]
    return value
