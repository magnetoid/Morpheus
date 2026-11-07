"""The CRM's leads, for its own Leads tab and for the dashboard's Contacts list.

Contacts lists accounts. A lead is someone the store has an address for and no
account: a newsletter signup, a contact form, a support chat. Contacts asks for
them through ``CONTACTS_LEADS`` and the CRM answers here, so the shell imports
nothing of the CRM and the leads leave Contacts with the app.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db.models import Exists, OuterRef, Q


def leads_matching(search: str = ''):
    """Every lead, narrowed to `search` (email, name or company)."""
    from plugins.installed.crm.models import Lead  # noqa: PLC0415

    qs = Lead.objects.all()
    if search:
        qs = qs.filter(
            Q(email__icontains=search)
            | Q(first_name__icontains=search)
            | Q(last_name__icontains=search)
            | Q(company__icontains=search)
        )
    return qs


def _row(lead) -> dict:
    return {
        'email': lead.email,
        'name': f'{lead.first_name} {lead.last_name}'.strip(),
        'source_display': lead.get_source_display(),
        'status': lead.status,
        'status_display': lead.get_status_display(),
        'created_at': lead.created_at,
    }


def contacts_leads(value, search: str = '', request=None, **kwargs):
    """``CONTACTS_LEADS`` answer: leads without an account, for staff who may read the CRM.

    A converted lead, or one whose address already has an account (someone who
    signed up for the newsletter after registering), is listed in Contacts as
    that account, so it is left out here.
    """
    if value is not None:
        return value
    from core.authz import check  # noqa: PLC0415

    user = getattr(request, 'user', None)
    if user is None or not check(user, 'crm.read', target='contacts.leads'):
        return value
    accounts = get_user_model().objects.filter(email__iexact=OuterRef('email'))
    queryset = leads_matching(search).exclude(status='converted').exclude(Exists(accounts))
    return {'queryset': queryset, 'row': _row}
