"""Agent commands for the newsletter — lets Linda read the list, see stats, and
create / toggle signup popups. Contributed via
`NewsletterPlugin.contribute_agent_tools` (present only while enabled).
Campaigns (C2): list, draft and send, with the dashboard composer's rules.
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


# ── Campaigns (C2) ──────────────────────────────────────────────────────────
# The same rules as the dashboard composer (newsletter/campaigns.py). Both writes
# need the merchant's own yes: a draft goes to the list later, a send goes now.

_AUDIENCE_HELP = (
    "audience: '' (every confirmed subscriber) or an RFM segment: champions, loyal, "
    'potential, new, at_risk, lost. A segment only narrows the confirmed list.'
)


def _campaign_row(c) -> dict:
    from plugins.installed.newsletter.campaigns import is_missed

    return {
        'id': str(c.id),
        'name': c.name,
        'subject': c.subject,
        'status': c.status,
        'audience': c.audience,
        'scheduled_at': c.scheduled_at.isoformat() if c.scheduled_at else None,
        'missed': is_missed(c),
        'recipient_count': c.recipient_count,
    }


@tool(
    name='newsletter.campaigns',
    description='List newsletter campaigns, newest first: status, audience, send time, '
    'whether a schedule was missed, and how many people each reached.',
    scopes=['promotions.read'],
    schema={
        'type': 'object',
        'properties': {'limit': {'type': 'integer', 'minimum': 1, 'maximum': 50, 'default': 20}},
    },
)
def newsletter_campaigns_tool(*, limit: int = 20) -> ToolResult:
    from plugins.installed.marketing.models import EmailCampaign

    try:
        limit = max(1, min(50, int(limit)))
    except (TypeError, ValueError):
        limit = 20
    rows = [_campaign_row(c) for c in EmailCampaign.objects.all()[:limit]]
    return ToolResult(output={'campaigns': rows}, display=f'{len(rows)} campaign(s).')


@tool(
    name='newsletter.campaign_create',
    description='Write a newsletter campaign as a draft (sent later with '
    'newsletter.campaign_send). body_html is rich HTML; it is cleaned and sent in the '
    "store's email look with an unsubscribe link. " + _AUDIENCE_HELP,
    scopes=['promotions.write'],
    requires_approval=True,
    schema={
        'type': 'object',
        'properties': {
            'name': {'type': 'string'},
            'subject': {'type': 'string'},
            'body_html': {'type': 'string'},
            'preview_text': {'type': 'string'},
            'audience': {
                'type': 'string',
                'enum': ['', 'champions', 'loyal', 'potential', 'new', 'at_risk', 'lost'],
            },
        },
        'required': ['name', 'subject', 'body_html'],
    },
)
def newsletter_campaign_create_tool(
    *, name: str, subject: str, body_html: str, preview_text: str = '', audience: str = ''
) -> ToolResult:
    from plugins.installed.newsletter.campaigns import CampaignError, save_campaign

    try:
        c = save_campaign(
            name=name,
            subject=subject,
            preview_text=preview_text,
            html_body=body_html,
            audience=audience,
        )
    except CampaignError as e:
        return ToolResult(output={'error': str(e)})
    return ToolResult(
        output={'id': str(c.id), 'status': c.status},
        display=f'Drafted campaign “{c.name}”.',
    )


@tool(
    name='newsletter.campaign_send',
    description='Send a draft newsletter campaign now, or schedule it with send_at '
    '(ISO 8601 with a UTC offset, e.g. 2026-12-01T09:00:00+01:00). A campaign more than '
    'a day past its time is not sent.',
    scopes=['promotions.write'],
    requires_approval=True,
    schema={
        'type': 'object',
        'properties': {'campaign_id': {'type': 'string'}, 'send_at': {'type': 'string'}},
        'required': ['campaign_id'],
    },
)
def newsletter_campaign_send_tool(*, campaign_id: str, send_at: str = '') -> ToolResult:
    from django.core.exceptions import ValidationError
    from django.utils import timezone
    from django.utils.dateparse import parse_datetime

    from plugins.installed.marketing.models import EmailCampaign
    from plugins.installed.newsletter.campaigns import (
        CampaignError,
        schedule_campaign,
        send_campaign_now,
    )

    try:
        c = EmailCampaign.objects.get(pk=campaign_id)
    except (EmailCampaign.DoesNotExist, ValidationError, ValueError):
        return ToolResult(output={'error': 'No campaign with that id.'})
    try:
        if (send_at or '').strip():
            when = parse_datetime(send_at.strip())
            if when is None or timezone.is_naive(when):
                raise CampaignError('send_at needs a date, a time and a UTC offset.')
            schedule_campaign(c, when)
        else:
            send_campaign_now(c)
    except CampaignError as e:
        return ToolResult(output={'error': str(e)})
    c.refresh_from_db()
    return ToolResult(
        output={'id': str(c.id), 'status': c.status},
        display=f'“{c.name}” is {c.status}.',
    )
