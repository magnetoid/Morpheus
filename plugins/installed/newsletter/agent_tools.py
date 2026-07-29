"""Agent commands for the newsletter — lets Linda read the list, see stats, and
create / toggle signup popups. Contributed via
`NewsletterPlugin.contribute_agent_tools` (present only while enabled).
Sending campaigns stays with the marketing plugin (Phase 3 broadcast).
"""

from __future__ import annotations

from core.agents.tools import ToolResult
from morpheus.core import tool


@tool(
    name='newsletter.stats',
    description='Newsletter overview: subscriber counts by status + the active signup popup.',
    scopes=['analytics.read'],
    schema={'type': 'object', 'properties': {}},
)
def newsletter_stats_tool() -> ToolResult:
    from django.db.models import Count

    from plugins.installed.newsletter.models import NewsletterSubscriber, SignupPopup

    counts = {
        r['status']: r['n']
        for r in NewsletterSubscriber.objects.values('status').annotate(n=Count('id'))
    }
    active = SignupPopup.objects.filter(enabled=True).order_by('-updated_at').first()
    return ToolResult(
        output={
            'confirmed': counts.get('confirmed', 0),
            'pending': counts.get('pending', 0),
            'unsubscribed': counts.get('unsubscribed', 0),
            'total': sum(counts.values()),
            'active_popup': active.name if active else None,
        },
        display=f'{counts.get("confirmed", 0)} confirmed subscriber(s).',
    )


@tool(
    name='newsletter.list_subscribers',
    description='List newsletter subscribers, newest first. Filter by status '
    '(pending/confirmed/unsubscribed).',
    scopes=['crm.read'],
    schema={
        'type': 'object',
        'properties': {
            'status': {'type': 'string'},
            'limit': {'type': 'integer', 'minimum': 1, 'maximum': 100, 'default': 25},
        },
    },
)
def newsletter_list_subscribers_tool(*, status: str = '', limit: int = 25) -> ToolResult:
    from plugins.installed.newsletter.models import NewsletterSubscriber

    qs = NewsletterSubscriber.objects.all()
    if status.strip() in {'pending', 'confirmed', 'unsubscribed'}:
        qs = qs.filter(status=status.strip())
    try:
        n = max(1, min(int(limit or 25), 100))
    except (TypeError, ValueError):
        n = 25
    rows = [
        {
            'email': s.email,
            'status': s.status,
            'source': s.source,
            'joined': s.created_at.date().isoformat(),
        }
        for s in qs[:n]
    ]
    return ToolResult(
        output={'subscribers': rows, 'count': len(rows)}, display=f'{len(rows)} subscriber(s).'
    )


@tool(
    name='newsletter.create_popup',
    description=(
        'Create a signup popup. Created disabled — review then enable with '
        'newsletter.toggle_popup. trigger: immediate|time_delay|exit_intent|'
        'scroll_depth; trigger_value is seconds (time_delay) or percent (scroll).'
    ),
    scopes=['content.write'],
    schema={
        'type': 'object',
        'properties': {
            'name': {'type': 'string'},
            'headline': {'type': 'string'},
            'body': {'type': 'string'},
            'incentive': {'type': 'string'},
            'trigger': {'type': 'string'},
            'trigger_value': {'type': 'integer'},
        },
        'required': ['name'],
    },
)
def newsletter_create_popup_tool(
    *,
    name: str,
    headline: str = '',
    body: str = '',
    incentive: str = '',
    trigger: str = 'time_delay',
    trigger_value: int = 5,
) -> ToolResult:
    from plugins.installed.newsletter.models import SignupPopup

    if not (name or '').strip():
        return ToolResult(output={'error': 'name is required'})
    valid_triggers = {c[0] for c in SignupPopup.TRIGGER_CHOICES}
    if trigger not in valid_triggers:
        trigger = 'time_delay'
    try:
        tv = max(0, int(trigger_value))
    except (TypeError, ValueError):
        tv = 5
    popup = SignupPopup.objects.create(
        name=name.strip()[:120],
        headline=(headline or 'Join our newsletter').strip()[:200],
        body=(body or '').strip(),
        incentive=(incentive or '').strip()[:120],
        trigger=trigger,
        trigger_value=tv,
    )
    return ToolResult(
        output={'id': str(popup.id), 'name': popup.name, 'enabled': popup.enabled},
        display=f'Created popup “{popup.name}” (disabled — enable when ready).',
    )


@tool(
    name='newsletter.toggle_popup',
    description='Enable or disable a signup popup by id. Only one enabled popup '
    'shows at a time (most recently updated).',
    scopes=['content.write'],
    schema={
        'type': 'object',
        'properties': {
            'popup_id': {'type': 'string'},
            'enabled': {'type': 'boolean'},
        },
        'required': ['popup_id', 'enabled'],
    },
)
def newsletter_toggle_popup_tool(*, popup_id: str, enabled: bool) -> ToolResult:
    from plugins.installed.newsletter.models import SignupPopup

    popup = SignupPopup.objects.filter(id=popup_id).first()
    if popup is None:
        return ToolResult(output={'error': f'no popup {popup_id!r}'})
    popup.enabled = bool(enabled)
    popup.save(update_fields=['enabled', 'updated_at'])
    return ToolResult(
        output={'id': str(popup.id), 'name': popup.name, 'enabled': popup.enabled},
        display=f'Popup “{popup.name}” {"enabled" if popup.enabled else "disabled"}.',
    )
