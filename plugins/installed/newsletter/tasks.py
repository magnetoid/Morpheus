"""Campaign + lifecycle sending — newsletter Phase 3 (the send path).

The audience, tokens, and consent live here; the campaign *content* is
marketing's ``EmailCampaign`` (cross-plugin read sanctioned by
``requires=['marketing']``); delivery rides the core async sender
(``core.emails.tasks.deliver_email``, per-recipient retries) with the
RFC 8058 one-click-unsubscribe header pair Gmail/Yahoo require of bulk
senders. Idempotency lives in the ``CampaignSend`` ledger, never in
memory — a re-run (worker restart, double click) skips logged recipients.
"""

# ruff: noqa: PLC0415
# Inline imports keep this module importable before the app registry is
# ready (mirrors the sibling services module).
from __future__ import annotations

import logging
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.utils import timezone
from django.utils.html import strip_tags

logger = logging.getLogger('morpheus.newsletter')

# One win-back per address per window — a lapsed reader who stays lapsed
# must not be nagged monthly-forever by the nightly segment rescore.
WINBACK_COOLDOWN_DAYS = 30


def _unsubscribe_headers(token: str) -> dict:
    """The RFC 8058 one-click pair for one recipient's unsubscribe token."""
    from plugins.installed.newsletter.services import _unsubscribe_url

    return {
        'List-Unsubscribe': f'<{_unsubscribe_url(token)}>',
        'List-Unsubscribe-Post': 'List-Unsubscribe=One-Click',
    }


def _base_bodies(campaign) -> tuple[str, str | None]:
    """The campaign's text/html bodies, constant across recipients. Computed
    once per send so the strip_tags fallback isn't re-run per subscriber."""
    text = (campaign.text_body or strip_tags(campaign.html_body or '')).strip()
    html = (campaign.html_body or '').strip() or None
    return text, html


def _with_footer(base_text: str, base_html: str | None, token: str) -> tuple[str, str | None]:
    """Append this recipient's one-click unsubscribe footer to the base bodies."""
    from plugins.installed.newsletter.services import _unsubscribe_url

    url = _unsubscribe_url(token)
    text = f'{base_text}\n\n—\nUnsubscribe: {url}\n'
    html = (
        f'{base_html}\n<p style="font-size:12px;color:#777;"><a href="{url}">Unsubscribe</a></p>'
        if base_html
        else None
    )
    return text, html


@shared_task(bind=True, time_limit=600, soft_time_limit=540)
def send_campaign(self, campaign_id: str) -> dict:
    """Send a campaign to every confirmed subscriber. Idempotent.

    Only a ``draft``/``scheduled`` campaign starts sending (re-invoking a
    sending/sent one is a no-op). Per recipient: skip anyone already in the
    ``CampaignSend`` ledger for this campaign, enqueue one ``deliver_email``
    (which owns SMTP retries), log the ledger row. Fail-soft per row — one
    bad address never stops the list.
    """
    from core.emails.tasks import deliver_email
    from plugins.installed.marketing.models import EmailCampaign
    from plugins.installed.newsletter.models import CampaignSend, NewsletterSubscriber

    try:
        campaign = EmailCampaign.objects.get(pk=campaign_id)
    except EmailCampaign.DoesNotExist:
        return {'ok': False, 'error': 'not-found'}
    if campaign.status not in ('draft', 'scheduled'):
        return {'ok': False, 'error': f'status-{campaign.status}'}
    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', '') or ''
    if not from_email:
        return {'ok': False, 'error': 'no-from-email'}

    # Atomically CLAIM the campaign: only the worker that flips draft/scheduled →
    # sending proceeds. A conditional UPDATE is the lock — a double-click "Send"
    # or a Celery retry firing alongside the first run gets 0 rows here and bails,
    # instead of both passing the read-check above and blasting the whole list
    # twice. (A crash after this leaves the campaign 'sending'; the CampaignSend
    # ledger below still de-dupes a manual re-send once it's reset to draft.)
    claimed = EmailCampaign.objects.filter(
        pk=campaign.pk, status__in=('draft', 'scheduled')
    ).update(status='sending')
    if not claimed:
        return {'ok': False, 'error': 'already-claimed'}

    already = set(CampaignSend.objects.filter(campaign=campaign).values_list('email', flat=True))
    base_text, base_html = _base_bodies(campaign)  # constant — computed once, not per row
    sent = failed = 0
    for sub in NewsletterSubscriber.objects.filter(status='confirmed').iterator():
        if sub.email in already:
            continue
        try:
            text, html = _with_footer(base_text, base_html, sub.confirm_token)
            deliver_email.delay(
                subject=campaign.subject,
                text_body=text,
                html_body=html,
                from_email=from_email,
                to=sub.email,
                headers=_unsubscribe_headers(sub.confirm_token),
            )
            CampaignSend.objects.create(campaign=campaign, email=sub.email)
            sent += 1
        except Exception as e:  # noqa: BLE001 — one bad row never stops the list
            failed += 1
            CampaignSend.objects.create(
                campaign=campaign, email=sub.email, ok=False, detail=str(e)[:200]
            )
            logger.warning('newsletter: campaign %s → %s failed: %s', campaign.pk, sub.email, e)

    EmailCampaign.objects.filter(pk=campaign.pk).update(
        status='sent',
        sent_at=timezone.now(),
        recipient_count=CampaignSend.objects.filter(campaign=campaign, ok=True).count(),
    )
    logger.info(
        'newsletter: campaign %s sent=%s failed=%s skipped=%s',
        campaign.pk,
        sent,
        failed,
        len(already),
    )
    return {'ok': True, 'sent': sent, 'failed': failed, 'skipped': len(already)}


@shared_task(bind=True, time_limit=120, soft_time_limit=90)
def send_campaign_test(self, campaign_id: str, to: str) -> dict:
    """Send one test copy to ``to`` — no status change, no audience touch."""
    from core.emails.tasks import deliver_email
    from plugins.installed.marketing.models import EmailCampaign
    from plugins.installed.newsletter.models import CampaignSend

    try:
        campaign = EmailCampaign.objects.get(pk=campaign_id)
    except EmailCampaign.DoesNotExist:
        return {'ok': False, 'error': 'not-found'}
    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', '') or ''
    if not from_email or not to:
        return {'ok': False, 'error': 'no-address'}
    text, html = _base_bodies(campaign)  # no footer/headers on a test copy
    deliver_email.delay(
        subject=f'[test] {campaign.subject}',
        text_body=text,
        html_body=html,
        from_email=from_email,
        to=to,
    )
    CampaignSend.objects.create(campaign=campaign, kind='test', email=to)
    return {'ok': True}


def send_winback(customer) -> bool:
    """Win-back email to a newly at-risk customer — consent-gated, deduped.

    Consent = a CONFIRMED newsletter subscription for the customer's email:
    the double opt-in is the explicit marketing consent, and it supplies the
    unsubscribe token the RFC 8058 headers need. No subscription → no email,
    ever. Dedupe: one win-back per address per ``WINBACK_COOLDOWN_DAYS``.
    Returns True when an email was actually queued.
    """
    from plugins.installed.newsletter.models import CampaignSend, NewsletterSubscriber

    email = (getattr(customer, 'email', '') or '').strip()
    if not email:
        return False
    sub = NewsletterSubscriber.objects.filter(email__iexact=email, status='confirmed').first()
    if sub is None:
        return False
    cutoff = timezone.now() - timedelta(days=WINBACK_COOLDOWN_DAYS)
    if CampaignSend.objects.filter(
        kind='winback', email__iexact=email, created_at__gte=cutoff
    ).exists():
        return False

    from plugins.registry import plugin_registry

    coupon_code = str(plugin_registry.config_value('newsletter', 'winback_coupon_code', '') or '')

    from core.emails import send_templated_email
    from core.utils.site import site_base_url
    from plugins.installed.newsletter.services import _unsubscribe_url

    send_templated_email(
        'newsletter_winback',
        to=email,
        subject='We saved some books for you',
        ctx={
            'customer': customer,
            'first_name': (getattr(customer, 'first_name', '') or '').strip(),
            'store_url': site_base_url(),
            'coupon_code': coupon_code,
            'unsubscribe_url': _unsubscribe_url(sub.confirm_token),
        },
        headers=_unsubscribe_headers(sub.confirm_token),
    )
    CampaignSend.objects.create(kind='winback', email=email)
    return True
