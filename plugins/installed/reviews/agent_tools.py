"""Agent commands for review moderation. The Review model is owned by catalog
(`requires = ['catalog']`); these tools let Linda triage the moderation queue —
list pending reviews, approve them, or delete spam. Contributed via
`ReviewsPlugin.contribute_agent_tools`, so they vanish when reviews is disabled.
"""

from __future__ import annotations

from core.agents import tool
from core.agents.tools import ToolResult


def _brief(r) -> dict:
    return {
        'id': str(r.id),
        'product': getattr(r.product, 'slug', '') or str(r.product_id),
        'rating': r.rating,
        'title': r.title,
        'body': (r.body or '')[:280],
        'is_approved': r.is_approved,
        'verified_purchase': r.is_verified_purchase,
        'created_at': r.created_at.isoformat() if r.created_at else None,
    }


@tool(
    name='reviews.list_pending',
    description='List product reviews awaiting moderation (not yet approved), newest first.',
    scopes=['catalog.read'],
    schema={
        'type': 'object',
        'properties': {'limit': {'type': 'integer', 'minimum': 1, 'maximum': 50, 'default': 20}},
    },
)
def reviews_list_pending_tool(*, limit: int = 20) -> ToolResult:
    from plugins.installed.catalog.models import Review

    try:
        n = max(1, min(int(limit or 20), 50))
    except (TypeError, ValueError):
        n = 20
    rows = [
        _brief(r)
        for r in Review.objects.select_related('product')
        .filter(is_approved=False)
        .order_by('-created_at')[:n]
    ]
    return ToolResult(
        output={'pending': rows, 'count': len(rows)}, display=f'{len(rows)} pending review(s).'
    )


def _get(review_id: str):
    from plugins.installed.catalog.models import Review

    return Review.objects.select_related('product').filter(id=review_id).first()


@tool(
    name='reviews.approve',
    description='Approve a pending review so it appears on the storefront.',
    scopes=['catalog.write'],
    schema={
        'type': 'object',
        'properties': {'review_id': {'type': 'string'}},
        'required': ['review_id'],
    },
)
def reviews_approve_tool(*, review_id: str) -> ToolResult:
    r = _get(review_id)
    if r is None:
        return ToolResult(output={'error': f'no review {review_id!r}'})
    if not r.is_approved:
        r.is_approved = True
        r.save(update_fields=['is_approved', 'updated_at'])
    return ToolResult(output=_brief(r), display='Review approved.')


@tool(
    name='reviews.delete',
    description=(
        'Delete a review (spam / abuse). Permanent — confirm with the user first. '
        'To merely keep a review hidden, leave it unapproved instead.'
    ),
    scopes=['catalog.write'],
    schema={
        'type': 'object',
        'properties': {'review_id': {'type': 'string'}},
        'required': ['review_id'],
    },
)
def reviews_delete_tool(*, review_id: str) -> ToolResult:
    r = _get(review_id)
    if r is None:
        return ToolResult(output={'error': f'no review {review_id!r}'})
    brief = _brief(r)
    r.delete()
    return ToolResult(output={'deleted': True, 'review': brief}, display='Review deleted.')
