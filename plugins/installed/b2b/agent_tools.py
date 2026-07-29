"""B2B agent tools."""

# ruff: noqa: PLC0415
from __future__ import annotations

from morpheus.core import ToolError, ToolResult, tool


@tool(
    name='b2b.list_quotes',
    description='List recent quotes, optionally filtered by state.',
    scopes=['b2b.read'],
    schema={
        'type': 'object',
        'properties': {
            'state': {
                'type': 'string',
                'enum': [
                    'draft',
                    'sent',
                    'viewed',
                    'accepted',
                    'rejected',
                    'expired',
                    'converted',
                ],
            },
            'limit': {'type': 'integer', 'minimum': 1, 'maximum': 50, 'default': 25},
        },
    },
)
def list_quotes_tool(*, state: str = '', limit: int = 25) -> ToolResult:
    from plugins.installed.b2b.models import Quote

    qs = Quote.objects.select_related('account', 'contact').order_by('-created_at')
    if state:
        qs = qs.filter(state=state)
    rows = list(qs[: max(1, min(int(limit or 25), 50))])
    return ToolResult(
        output={
            'quotes': [
                {
                    'quote_number': q.quote_number,
                    'state': q.state,
                    'account': q.account.name if q.account_id else '',
                    'total': str(q.total.amount),
                    'created_at': q.created_at.isoformat(),
                }
                for q in rows
            ],
        }
    )


@tool(
    name='b2b.set_net_terms',
    description='Set net-N payment terms for a B2B account.',
    scopes=['b2b.write'],
    schema={
        'type': 'object',
        'properties': {
            'account_name': {'type': 'string'},
            'net_days': {'type': 'integer', 'enum': [15, 30, 45, 60, 90]},
        },
        'required': ['account_name', 'net_days'],
    },
    requires_approval=True,
)
def set_net_terms_tool(*, account_name: str, net_days: int) -> ToolResult:
    from plugins.installed.b2b.models import NetTermsAgreement
    from plugins.installed.crm.models import Account

    try:
        account = Account.objects.get(name__iexact=account_name)
    except Account.DoesNotExist as e:
        raise ToolError(f'Unknown account: {account_name}') from e
    nt, _ = NetTermsAgreement.objects.update_or_create(
        account=account,
        defaults={'net_days': int(net_days), 'is_active': True},
    )
    return ToolResult(
        output={'account': account.name, 'net_days': nt.net_days},
        display=f'Net {nt.net_days} for {account.name}',
    )
