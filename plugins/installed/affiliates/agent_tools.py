"""Affiliate agent tools."""

from __future__ import annotations

from core.agents import ToolError, ToolResult, tool


@tool(
    name='affiliates.list_affiliates',
    description='List affiliates with their lifetime click/conversion/payout totals.',
    scopes=['affiliates.read'],
    schema={
        'type': 'object',
        'properties': {
            'limit': {'type': 'integer', 'minimum': 1, 'maximum': 100, 'default': 25},
        },
    },
)
def list_affiliates_tool(*, limit: int = 25) -> ToolResult:
    """List affiliates with aggregated KPIs.

    Counters live on AffiliateLink, not Affiliate. Sum them per
    affiliate via .annotate() instead of dereferencing fields that
    don't exist on the parent row.
    """
    from django.db.models import Sum

    from plugins.installed.affiliates.models import Affiliate

    cap = max(1, min(int(limit or 25), 100))
    rows = list(
        Affiliate.objects.select_related('user', 'program')
        .annotate(
            total_clicks=Sum('links__click_count'),
            total_conversions=Sum('links__conversion_count'),
        )
        .order_by('-lifetime_paid', '-created_at')[:cap]
    )
    return ToolResult(
        output={
            'affiliates': [
                {
                    'id': str(a.id),
                    'handle': a.handle,
                    'email': getattr(a.user, 'email', '') if a.user_id else '',
                    'program': a.program.name if a.program_id else '',
                    'status': a.status,
                    'click_count': a.total_clicks or 0,
                    'conversion_count': a.total_conversions or 0,
                    'lifetime_paid': str(getattr(a.lifetime_paid, 'amount', a.lifetime_paid or ''))
                    if a.lifetime_paid
                    else '0',
                    'accrued_balance': str(
                        getattr(a.accrued_balance, 'amount', a.accrued_balance or '')
                    )
                    if a.accrued_balance
                    else '0',
                }
                for a in rows
            ],
        }
    )


@tool(
    name='affiliates.pending_payouts',
    description='List affiliate payouts in pending state.',
    scopes=['affiliates.read'],
    schema={'type': 'object', 'properties': {}},
)
def pending_payouts_tool() -> ToolResult:
    from plugins.installed.affiliates.models import AffiliatePayout

    rows = list(
        AffiliatePayout.objects.filter(status='pending')
        .select_related('affiliate__user', 'affiliate__program')
        .order_by('-requested_at')[:50]
    )
    return ToolResult(
        output={
            'payouts': [
                {
                    'id': str(p.id),
                    'affiliate_handle': p.affiliate.handle,
                    'affiliate_email': getattr(p.affiliate.user, 'email', ''),
                    'amount': str(p.amount.amount),
                    'currency': str(p.amount.currency),
                    'method': p.method,
                    'requested_at': p.requested_at.isoformat(),
                }
                for p in rows
            ],
        }
    )


@tool(
    name='affiliates.mark_payout_paid',
    description='Mark a pending affiliate payout as paid (after external transfer).',
    scopes=['affiliates.write'],
    schema={
        'type': 'object',
        'properties': {
            'payout_id': {'type': 'string'},
            'external_reference': {'type': 'string', 'description': 'Bank/Stripe ref id'},
        },
        'required': ['payout_id'],
    },
    requires_approval=True,
)
def mark_payout_paid_tool(*, payout_id: str, external_reference: str = '') -> ToolResult:
    from plugins.installed.affiliates.models import AffiliatePayout
    from plugins.installed.affiliates.services import mark_payout_paid

    try:
        payout = AffiliatePayout.objects.get(id=payout_id)
    except AffiliatePayout.DoesNotExist as e:
        raise ToolError(f'Unknown payout: {payout_id}') from e
    mark_payout_paid(payout, external_reference=external_reference)
    return ToolResult(
        output={'payout_id': str(payout.id), 'status': payout.status},
        display=f'Marked payout {payout.id} paid',
    )


@tool(
    name='affiliates.create_affiliate',
    description='Create a new affiliate from a customer email.',
    scopes=['affiliates.write'],
    schema={
        'type': 'object',
        'properties': {
            'email': {'type': 'string'},
            'program_name': {
                'type': 'string',
                'description': 'Optional program; defaults to first active program.',
            },
            'code': {
                'type': 'string',
                'description': 'Optional custom code; auto-generated if omitted.',
            },
        },
        'required': ['email'],
    },
    requires_approval=True,
)
def create_affiliate_tool(*, email: str, program_name: str = '', handle: str = '') -> ToolResult:
    """Create (or fetch) an affiliate from a customer email + program.

    Affiliate identifies via ``user`` (auth User) + ``handle`` (unique
    slug). The agent passes a handle to override; otherwise we derive
    one from the email local-part with a short random tail to avoid
    handle collisions.
    """
    import secrets

    from django.contrib.auth import get_user_model
    from django.utils.text import slugify

    from plugins.installed.affiliates.models import Affiliate, AffiliateProgram

    User = get_user_model()
    user = User.objects.filter(email__iexact=email).first()
    if not user:
        raise ToolError(f'No customer with email {email}')
    program = (
        AffiliateProgram.objects.filter(name__iexact=program_name).first()
        if program_name
        else AffiliateProgram.objects.filter(is_active=True).order_by('-created_at').first()
    )
    if not program:
        raise ToolError('No active affiliate program. Create one in admin first.')
    if not handle:
        local = email.split('@', 1)[0]
        handle = f'{slugify(local)[:60]}-{secrets.token_urlsafe(3)[:6]}'.strip('-')
    affiliate, created = Affiliate.objects.get_or_create(
        user=user,
        program=program,
        defaults={'handle': handle, 'status': 'pending', 'payout_email': email},
    )
    return ToolResult(
        output={
            'affiliate_id': str(affiliate.id),
            'handle': affiliate.handle,
            'status': affiliate.status,
            'created': created,
        },
        display=f'{"Created" if created else "Found"} affiliate {affiliate.handle}',
    )
