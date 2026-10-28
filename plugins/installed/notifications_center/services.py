"""Public API: `notify(user, kind, title, ...)`.

Plugins call this instead of writing Notification rows directly so the
fan-in stays centralised: per-user preferences (muted kinds), stacking of
repeats and the default level of each kind are decided here, once.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from datetime import datetime, timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.db.models.functions import Coalesce
from django.utils import timezone

from plugins.installed.notifications_center.models import (
    LEVELS,
    Notification,
    NotificationPreference,
)

logger = logging.getLogger('morpheus.notifications_center')

#: The kinds the store sends today: what staff see on the settings page, and the
#: level a notification gets when its sender names none.
KINDS: dict[str, tuple[str, str]] = {
    'returns.requested': ('Return requests', 'warning'),
    'inventory.low_stock': ('Low stock', 'warning'),
    'inventory.out_of_stock': ('Out of stock', 'urgent'),
    'inventory.stockout_forecast': ('Stock-out forecast', 'warning'),
    'agents.run_failed': ('Failed automatic tasks', 'warning'),
    'workflows.fired': ('Workflow alerts', 'info'),
}
#: A stack remembers this many occurrences; `count` keeps counting past it.
MAX_OCCURRENCES = 20
SNOOZE_CHOICES: dict[str, str] = {'hour': '1 hour', 'tomorrow': 'Tomorrow', 'week': 'Next week'}


def kind_label(kind: str) -> str:
    if kind in KINDS:
        return KINDS[kind][0]
    return (kind or '').replace('_', ' ').replace('.', ' · ').capitalize()


def _level_for(kind: str, level: str) -> str:
    if level in LEVELS:
        return level
    return KINDS.get(kind, ('', 'info'))[1]


def _higher(a: str, b: str) -> str:
    return a if LEVELS.index(a if a in LEVELS else 'info') >= LEVELS.index(b) else b


def muted_kinds(user) -> set[str]:
    if user is None or not getattr(user, 'pk', None):
        return set()
    pref = NotificationPreference.objects.filter(user=user).first()
    return {k for k in (pref.muted_kinds if pref else []) if isinstance(k, str)}


def set_muted(user, kind: str, muted: bool) -> set[str]:
    pref, _ = NotificationPreference.objects.get_or_create(user=user)
    kinds = {k for k in (pref.muted_kinds or []) if isinstance(k, str)}
    if muted:
        kinds.add(kind[:80])
    else:
        kinds.discard(kind)
    pref.muted_kinds = sorted(kinds)
    pref.save(update_fields=['muted_kinds', 'updated_at'])
    return kinds


def _deliver(*, user, kind, title, body, action_url, icon, level, group_key) -> Notification:
    now = timezone.now()
    entry = {'at': now.isoformat(), 'title': title, 'body': body[:500]}
    if group_key:
        with transaction.atomic():
            open_stack = (
                Notification.objects.select_for_update()
                .filter(user=user, group_key=group_key, read_at__isnull=True)
                .filter(archived_at__isnull=True)
                .order_by('-created_at')
                .first()
            )
            if open_stack is not None:
                open_stack.count = (open_stack.count or 1) + 1
                open_stack.occurrences = [entry, *open_stack.history][:MAX_OCCURRENCES]
                open_stack.title = title
                open_stack.body = body
                open_stack.action_url = action_url
                open_stack.icon = icon
                open_stack.level = _higher(open_stack.level, level)
                # A snoozed stack keeps its wake time; a repeat never pulls it back early.
                open_stack.last_at = max(open_stack.activity_at, now)
                open_stack.save(
                    update_fields=[
                        'count',
                        'occurrences',
                        'title',
                        'body',
                        'action_url',
                        'icon',
                        'level',
                        'last_at',
                    ]
                )
                return open_stack
    return Notification.objects.create(
        user=user,
        kind=kind,
        title=title,
        body=body,
        action_url=action_url,
        icon=icon,
        level=level,
        group_key=group_key,
        occurrences=[entry],
        last_at=now,
    )


def notify(
    *,
    user,
    kind: str,
    title: str,
    body: str = '',
    action_url: str = '',
    icon: str = 'bell',
    level: str = '',
    subject: str = '',
) -> Notification | None:
    """Create a notification for a single staff user, or stack it.

    `level` is info | warning | urgent (default: the kind's, from KINDS).
    `subject` names what the event is about (a variant id, an agent): a repeat
    with the same kind and subject lands on the open stack instead of a new row.
    Leave it empty for events that never repeat. Returns the row, or ``None``
    when the user muted the kind or the input is bad. Never raises —
    notifications are best-effort; a DB error logs and moves on.
    """
    if user is None or not getattr(user, 'pk', None):
        return None
    try:
        kind = (kind or '')[:80]
        if kind in muted_kinds(user):
            return None
        subject = str(subject or '').strip()
        return _deliver(
            user=user,
            kind=kind,
            title=(title or '')[:200],
            body=body or '',
            action_url=action_url[:500] if action_url else '',
            icon=icon[:40] if icon else 'bell',
            level=_level_for(kind, level),
            group_key=f'{kind}:{subject}'[:200] if subject else '',
        )
    except Exception as e:  # noqa: BLE001
        logger.warning('notify failed for user=%s kind=%s: %s', user.pk, kind, e, exc_info=True)
        return None


def notify_all_staff(
    *,
    kind: str,
    title: str,
    body: str = '',
    action_url: str = '',
    icon: str = 'bell',
    level: str = '',
    subject: str = '',
) -> int:
    """Fan out to every active staff user who hasn't muted `kind`.

    Returns the count actually written (stacked repeats included). Use this
    for events that don't have a single owner (e.g. "low stock on SKU XYZ",
    "agent run failed").
    """
    User = get_user_model()
    staff = User.objects.filter(is_staff=True, is_active=True)
    written = 0
    for u in staff:
        if (
            notify(
                user=u,
                kind=kind,
                title=title,
                body=body,
                action_url=action_url,
                icon=icon,
                level=level,
                subject=subject,
            )
            is not None
        ):
            written += 1
    return written


# ── Reading ──────────────────────────────────────────────────────────────


def ordered(qs):
    """Latest activity first; rows from before `last_at` existed sort by creation."""
    return qs.annotate(_activity=Coalesce('last_at', 'created_at')).order_by(
        '-_activity', '-created_at'
    )


def inbox(user, *, now: datetime | None = None):
    """Not archived, and not snoozed into the future."""
    now = now or timezone.now()
    return Notification.objects.filter(user=user, archived_at__isnull=True).filter(
        Q(snoozed_until__isnull=True) | Q(snoozed_until__lte=now)
    )


#: The order each list tab shows in (the inbox tabs are annotated by `ordered`).
TAB_ORDER = {'snoozed': 'snoozed_until', 'archived': '-archived_at'}


def listing(user, tab: str):
    """One tab of the list page: inbox, unread, snoozed or archived."""
    now = timezone.now()
    if tab == 'snoozed':
        return Notification.objects.filter(
            user=user, archived_at__isnull=True, snoozed_until__gt=now
        ).order_by('snoozed_until')
    if tab == 'archived':
        return Notification.objects.filter(user=user, archived_at__isnull=False).order_by(
            '-archived_at'
        )
    qs = inbox(user, now=now)
    if tab == 'unread':
        qs = qs.filter(read_at__isnull=True)
    return ordered(qs)


def own(user, notification_id) -> Notification | None:
    """The user's own notification with this id, or None (a malformed id included)."""
    try:
        return Notification.objects.filter(pk=str(notification_id or '').strip(), user=user).first()
    except (ValueError, ValidationError):
        return None


def unread_counts(user) -> dict[str, int]:
    """Unread stacks in the inbox, and how many of them are urgent."""
    if user is None or not getattr(user, 'pk', None):
        return {'unread': 0, 'urgent': 0}
    try:
        unread = inbox(user).filter(read_at__isnull=True)
        return {'unread': unread.count(), 'urgent': unread.filter(level='urgent').count()}
    except Exception as e:  # noqa: BLE001
        logger.debug('unread count failed: %s', e)
        return {'unread': 0, 'urgent': 0}


def unread_count_for(user) -> int:
    return unread_counts(user)['unread']


def latest_for(user, *, limit: int = 10) -> Iterable[Notification]:
    """Latest N inbox notifications for a user. Used by the topbar bell."""
    if user is None or not getattr(user, 'pk', None):
        return []
    try:
        return list(ordered(inbox(user))[: max(1, min(int(limit), 50))])
    except Exception as e:  # noqa: BLE001
        logger.debug('latest_for failed: %s', e)
        return []


def as_dict(n: Notification) -> dict:
    """The shape the bell and Linda read."""
    return {
        'id': str(n.id),
        'kind': n.kind,
        'kind_label': kind_label(n.kind),
        'title': n.title,
        'body': n.body[:240],
        'action_url': n.action_url,
        'icon': n.icon or 'bell',
        'level': n.level or 'info',
        'count': n.count or 1,
        'occurrences': [
            {
                'at': o.get('at', ''),
                'title': o.get('title', ''),
                'body': (o.get('body') or '')[:240],
            }
            for o in n.history[1:6]
        ],
        'read': n.read_at is not None,
        'archived': n.archived_at is not None,
        'snoozed_until': n.snoozed_until.isoformat() if n.snoozed_until else None,
        'last_at': n.activity_at.isoformat(),
    }


# ── Acting on one notification ───────────────────────────────────────────


def snooze_until(choice: str, *, now: datetime | None = None) -> datetime | None:
    """1 hour from now, or 09:00 store time tomorrow / in a week."""
    now = now or timezone.now()
    if choice == 'hour':
        return now + timedelta(hours=1)
    days = {'tomorrow': 1, 'week': 7}.get(choice)
    if days is None:
        return None
    local = timezone.localtime(now) + timedelta(days=days)
    return local.replace(hour=9, minute=0, second=0, microsecond=0)


#: action → (the fields it sets, given the row and now; the line for the user).
_FIELD_ACTIONS = {
    'read': (lambda n, now: {'read_at': n.read_at or now}, 'Marked read.'),
    'unread': (lambda n, now: {'read_at': None}, 'Marked unread.'),
    'archive': (
        lambda n, now: {'archived_at': now, 'read_at': n.read_at or now},
        'Archived.',
    ),
    'unarchive': (lambda n, now: {'archived_at': None}, 'Moved back to the inbox.'),
    'wake': (lambda n, now: {'snoozed_until': None, 'last_at': now}, 'Back in the inbox.'),
}
ACTIONS = (*_FIELD_ACTIONS, 'snooze', 'mute', 'unmute')


def apply(n: Notification, action: str, *, until: str = '') -> str:
    """Do `action` to the user's own notification; returns a line for the user.

    Raises ValueError on an unknown action or snooze choice.
    """
    now = timezone.now()
    if action in _FIELD_ACTIONS:
        changes, line = _FIELD_ACTIONS[action]
        fields = changes(n, now)
        for name, value in fields.items():
            setattr(n, name, value)
        n.save(update_fields=list(fields))
        return line
    if action == 'snooze':
        wake = snooze_until(until, now=now)
        if wake is None:
            raise ValueError(f'snooze for {", ".join(SNOOZE_CHOICES)}')
        # It comes back unread, at the top, when the snooze ends.
        n.snoozed_until = wake
        n.last_at = wake
        n.read_at = None
        n.save(update_fields=['snoozed_until', 'last_at', 'read_at'])
        return f'Snoozed until {timezone.localtime(wake):%a %d %b, %H:%M}.'
    if action in ('mute', 'unmute'):
        set_muted(n.user, n.kind, action == 'mute')
        verb = 'will no longer get' if action == 'mute' else 'will get'
        return f'You {verb} “{kind_label(n.kind)}” notifications.'
    raise ValueError(f'unknown action {action!r}; one of {", ".join(ACTIONS)}')


def known_kinds(user) -> list[tuple[str, str]]:
    """Every kind this user can choose about: the built-in ones plus any they received."""
    received = set(Notification.objects.filter(user=user).values_list('kind', flat=True).distinct())
    kinds = set(KINDS) | received | muted_kinds(user)
    return sorted(((k, kind_label(k)) for k in kinds if k), key=lambda kv: kv[1].casefold())
