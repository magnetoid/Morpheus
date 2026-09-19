"""Transactional emails for booking enquiries (best-effort, fail-soft).

A captured `Enquiry` is a lead — someone must hear about it. On submit we:
- notify the host (vendor owner's email) or a configured ops inbox, and
- send the guest a "we received your enquiry" confirmation.

Sending never raises: a mail outage must not break enquiry capture. Prod must
set EMAIL_HOST (SMTP) and, optionally, BOOKING_ENQUIRY_NOTIFY_EMAIL for the
ops fallback; otherwise sends are logged and skipped.
"""

from __future__ import annotations

import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives

logger = logging.getLogger('morpheus.booking.email')


def _store_name() -> str:
    return getattr(settings, 'STORE_NAME', 'the team')


def _from() -> str:
    return getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@example.com')


def _host_recipient(enquiry) -> str | None:
    """Vendor owner's email if available, else the configured ops inbox."""
    vendor = getattr(enquiry.service, 'vendor', None) if enquiry.service_id else None
    owner = getattr(vendor, 'owner', None)
    owner_email = getattr(owner, 'email', '') if owner else ''
    return owner_email or getattr(settings, 'BOOKING_ENQUIRY_NOTIFY_EMAIL', '') or _from()


def _selection_lines(enquiry) -> str:
    """Human-readable summary of the structured selection captured on the lead."""
    parts = []
    if enquiry.preferred_date:
        parts.append(f'Preferred date: {enquiry.preferred_date:%a %d %b %Y}')
    if enquiry.time_slot:
        parts.append(f'Departure: {enquiry.time_slot}')
    if enquiry.guests:
        parts.append(f'Guests: {enquiry.guests}')
    for t in (enquiry.tier_breakdown or []):
        parts.append(f"  · {t.get('qty')}× {t.get('name')}")
    for a in (enquiry.addons or []):
        parts.append(f"  + add-on: {a.get('qty')}× {a.get('name')}")
    return '\n'.join(parts)


def _send(subject: str, body: str, to: str) -> bool:
    if not to:
        return False
    try:
        EmailMultiAlternatives(subject, body, _from(), [to]).send(fail_silently=False)
        return True
    except Exception as e:  # noqa: BLE001 — SMTP outage / unconfigured; never break capture
        logger.warning('booking.email: send failed -> %s: %s', to, e)
        return False


def send_enquiry_host_notification(enquiry) -> bool:
    to = _host_recipient(enquiry)
    name = enquiry.service.name if enquiry.service_id else 'a listing'
    lines = _selection_lines(enquiry)
    body = (
        f'New enquiry for "{name}".\n\n'
        f'From: {enquiry.name or "(no name)"} <{enquiry.email}>\n'
        f'Phone: {enquiry.phone or "—"}\n'
        + (f'\n{lines}\n' if lines else '')
        + (f'\nMessage:\n{enquiry.message}\n' if enquiry.message else '')
        + '\nReply to the guest directly to follow up.\n'
    )
    return _send(f'New enquiry — {name}', body, to)


def send_enquiry_confirmation(enquiry) -> bool:
    name = enquiry.service.name if enquiry.service_id else 'your enquiry'
    body = (
        f'Hi {enquiry.name or "there"},\n\n'
        f'Thanks for your enquiry about "{name}". We\'ve passed it to the host, '
        f'who will be in touch shortly with availability and a price.\n\n'
        f'— {_store_name()}\n'
    )
    return _send(f'We received your enquiry — {name}', body, enquiry.email)


def notify_enquiry(enquiry) -> None:
    """Fire both emails, best-effort. Safe to call from the request path."""
    send_enquiry_host_notification(enquiry)
    send_enquiry_confirmation(enquiry)


# ── Accommodation (stays) enquiries ──────────────────────────────────────────

def _stay_host_recipient(enquiry) -> str | None:
    """Property owner's email if available, else the configured ops inbox."""
    prop = getattr(enquiry, 'property', None) if enquiry.property_id else None
    vendor = getattr(prop, 'vendor', None) if prop else None
    owner = getattr(vendor, 'owner', None)
    owner_email = getattr(owner, 'email', '') if owner else ''
    return owner_email or getattr(settings, 'BOOKING_ENQUIRY_NOTIFY_EMAIL', '') or _from()


def send_stay_enquiry_host_notification(enquiry) -> bool:
    to = _stay_host_recipient(enquiry)
    name = enquiry.property.name if enquiry.property_id else 'a property'
    parts = []
    if enquiry.check_in:
        parts.append(f'Check-in: {enquiry.check_in:%a %d %b %Y}')
    if enquiry.check_out:
        parts.append(f'Check-out: {enquiry.check_out:%a %d %b %Y}')
    if enquiry.room_type_id:
        parts.append(f'Room: {enquiry.room_type.name}')
    if enquiry.rooms:
        parts.append(f'Rooms: {enquiry.rooms}')
    if enquiry.adults:
        parts.append(f'Adults: {enquiry.adults}')
    if enquiry.children:
        parts.append(f'Children: {enquiry.children}')
    lines = '\n'.join(parts)
    body = (
        f'New stay enquiry for "{name}".\n\n'
        f'From: {enquiry.name or "(no name)"} <{enquiry.email}>\n'
        f'Phone: {enquiry.phone or "—"}\n'
        + (f'\n{lines}\n' if lines else '')
        + (f'\nMessage:\n{enquiry.message}\n' if enquiry.message else '')
        + '\nReply to the guest directly to follow up.\n'
    )
    return _send(f'New stay enquiry — {name}', body, to)


def notify_stay_enquiry(enquiry) -> None:
    """Best-effort host notification for a stay enquiry (never raises)."""
    try:
        send_stay_enquiry_host_notification(enquiry)
    except Exception:  # noqa: BLE001 — mail must never break capture
        logger.warning('booking.email: stay enquiry notify failed for %s', enquiry.pk)
