"""The rules for newsletter campaigns (C2): audience, rendering, scheduling, composing.

The dashboard views and Linda's tools both call these, so the two doors cannot
disagree. Content lives on marketing's ``EmailCampaign`` (``requires=['marketing']``);
the audience is newsletter's confirmed list, which a segment only narrows: nobody
who did not opt in is ever mailed.
"""

# ruff: noqa: PLC0415
from __future__ import annotations

import html as html_lib
from datetime import datetime, timedelta

from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.html import strip_tags

#: Where each recipient's own unsubscribe link goes. The campaign is rendered once
#: per batch with this in place, then personalised per recipient.
UNSUBSCRIBE_SENTINEL = '__morpheus_unsubscribe_url__'

#: '' is everyone confirmed; the rest are the customers app's RFM segment keys.
AUDIENCES: list[tuple[str, str]] = [
    ('', 'All confirmed subscribers'),
    ('champions', 'Champions'),
    ('loyal', 'Loyal'),
    ('potential', 'Potential'),
    ('new', 'New'),
    ('at_risk', 'At risk'),
    ('lost', 'Lost'),
]
_AUDIENCE_KEYS = {key for key, _label in AUDIENCES}


class CampaignError(ValueError):
    """A refusal worded for the merchant and for Linda."""


def audience_label(audience: str) -> str:
    return dict(AUDIENCES).get(audience or '', audience)


def audience_emails(audience: str) -> set[str] | None:
    """The lower-cased emails a segment allows; ``None`` for everyone confirmed."""
    if not audience:
        return None
    if audience not in _AUDIENCE_KEYS:
        raise CampaignError('Unknown audience.')
    from core.hooks import MorpheusEvents, hook_registry

    answer = hook_registry.filter(MorpheusEvents.CUSTOMER_SEGMENT_EMAILS, None, segment=audience)
    if answer is None:
        raise CampaignError('The customers app is off, so a segment cannot be used.')
    return {e.lower() for e in answer}


def plain_text(html: str) -> str:
    """Readable text from rich HTML: block ends become line breaks."""
    spaced = html.replace('</p>', '</p>\n\n').replace('<br>', '\n').replace('</li>', '</li>\n')
    return html_lib.unescape(strip_tags(spaced)).strip()


def render_campaign(campaign) -> tuple[str, str]:
    """``(text, html)`` in the store layout, with the sentinel for the unsubscribe link.

    The body is sanitised here as well as on save, for rows written before C2.
    """
    from core.utils.html import sanitize_richtext
    from core.utils.site import store_name

    body = sanitize_richtext(campaign.html_body or '') or ''
    html = render_to_string(
        'emails/newsletter_campaign.html',
        {
            'subject': campaign.subject,
            'preview_text': campaign.preview_text,
            'body': body,
            'store_name': store_name(),
            'unsubscribe_url': UNSUBSCRIBE_SENTINEL,
        },
    )
    text = (campaign.text_body or plain_text(body)).strip()
    text = f'{text}\n\n—\nUnsubscribe: {UNSUBSCRIBE_SENTINEL}\n'
    return text, html


def personalise(text: str, html: str, unsubscribe_url: str) -> tuple[str, str]:
    return (
        text.replace(UNSUBSCRIBE_SENTINEL, unsubscribe_url),
        html.replace(UNSUBSCRIBE_SENTINEL, unsubscribe_url),
    )


# ── Scheduling ──────────────────────────────────────────────────────────────

#: A scheduled campaign this far past its time (workers were down) is not sent:
#: a sale announced days late is worse than one not sent. It goes back to draft.
MISSED_AFTER = timedelta(hours=24)


def schedule_campaign(campaign, when: datetime) -> None:
    """Send ``campaign`` at ``when`` (aware). Only a draft or scheduled one moves."""
    if campaign.status not in ('draft', 'scheduled'):
        raise CampaignError(f'"{campaign.name}" is {campaign.status} and cannot be scheduled.')
    if when is None or timezone.is_naive(when) or when <= timezone.now():
        raise CampaignError('Pick a time in the future.')
    campaign.status = 'scheduled'
    campaign.scheduled_at = when
    campaign.save(update_fields=['status', 'scheduled_at'])


def cancel_campaign(campaign) -> None:
    """Take a scheduled campaign back to an editable draft with no time."""
    if campaign.status != 'scheduled':
        raise CampaignError(f'"{campaign.name}" is {campaign.status}, not scheduled.')
    campaign.status = 'draft'
    campaign.scheduled_at = None
    campaign.save(update_fields=['status', 'scheduled_at'])


def is_missed(campaign) -> bool:
    """A draft that still carries a past send time: its slot went by unsent."""
    return bool(
        campaign.status == 'draft'
        and campaign.scheduled_at
        and campaign.scheduled_at < timezone.now()
    )
