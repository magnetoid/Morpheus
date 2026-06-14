"""Agent commands for loyalty points — lets Linda read a customer's balance +
tier and make manual point adjustments. Contributed via
`LoyaltyPlugin.contribute_agent_tools`, so they appear in Linda's catalogue
only while the plugin is enabled.
"""

from __future__ import annotations

from core.agents import tool
from core.agents.tools import ToolResult


def _find_customer(email: str):
    from django.contrib.auth import get_user_model

    return get_user_model().objects.filter(email__iexact=(email or '').strip()).first()


def _current_tier(customer) -> str:
    from plugins.installed.loyalty_points.models import CustomerTier

    ct = CustomerTier.objects.filter(customer=customer).select_related('tier').first()
    return ct.tier.label if (ct and ct.tier_id) else ''


@tool(
    name='loyalty.balance',
    description="Look up a customer's loyalty points balance and current tier by email.",
    scopes=['crm.read'],
    schema={
        'type': 'object',
        'properties': {'email': {'type': 'string', 'description': 'Customer email.'}},
        'required': ['email'],
    },
)
def loyalty_balance_tool(*, email: str) -> ToolResult:
    from plugins.installed.loyalty_points.services import get_balance

    cust = _find_customer(email)
    if cust is None:
        return ToolResult(output={'error': f'no customer with email {email!r}'})
    bal = get_balance(cust)
    return ToolResult(
        output={'email': cust.email, 'points': bal, 'tier': _current_tier(cust)},
        display=f'{cust.email}: {bal} pts',
    )


@tool(
    name='loyalty.adjust_points',
    description=(
        'Add or remove loyalty points for a customer. Use a NEGATIVE amount to '
        'deduct. Always confirm with the user before deducting points.'
    ),
    scopes=['crm.write'],
    schema={
        'type': 'object',
        'properties': {
            'email': {'type': 'string', 'description': 'Customer email.'},
            'points': {'type': 'integer', 'description': 'Positive adds, negative removes.'},
            'reason': {'type': 'string', 'description': 'Why — shown in the ledger.'},
        },
        'required': ['email', 'points'],
    },
)
def loyalty_adjust_points_tool(
    *, email: str, points: int, reason: str = 'manual_adjust'
) -> ToolResult:
    from plugins.installed.loyalty_points.services import award_points, get_balance

    cust = _find_customer(email)
    if cust is None:
        return ToolResult(output={'error': f'no customer with email {email!r}'})
    try:
        pts = int(points)
    except (TypeError, ValueError):
        return ToolResult(output={'error': 'points must be an integer'})
    if pts == 0:
        return ToolResult(output={'error': 'points must be non-zero'})

    award_points(cust, pts, reason=(reason or 'manual_adjust')[:40])
    new_balance = get_balance(cust)
    return ToolResult(
        output={'email': cust.email, 'adjusted': pts, 'new_balance': new_balance},
        display=f'{cust.email}: {pts:+d} → {new_balance} pts',
    )
