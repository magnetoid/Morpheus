"""The error report handed to Claude Code (docs/plans/detailed-error-capture-2026-10.md).

One builder, three doors: "Copy for Claude Code" and the downloads on the
error log page, ``manage.py errors_report`` in the store's container, and the
``errors.recent`` / ``errors.get`` agent tools.

A group is one fingerprint. It is *open* until someone resolves it; a resolved
group whose error fires again after the resolution is *regressed*, which counts
as open. Groups are ordered errors first, then by how often they fired.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

_LEVEL_RANK = {'error': 0, 'warning': 1, 'info': 2}
_SCAN = 400  # groups looked at before ranking (newest first)


def _states(fingerprints: list[str]) -> dict:
    from core.errors.models import ErrorGroup

    return {g.fingerprint: g for g in ErrorGroup.objects.filter(fingerprint__in=fingerprints)}


def status_of(group_state, last_seen) -> str:
    """open | resolved | regressed, from the decision and the latest event."""
    if group_state is None or group_state.status != 'resolved' or group_state.resolved_at is None:
        return 'open'
    return 'regressed' if last_seen > group_state.resolved_at else 'resolved'


def _event(e) -> dict[str, Any]:
    return {
        'at': e.created_at.isoformat(),
        'kind': e.kind,
        'level': e.level,
        'exception_class': e.exception_class,
        'message': e.message,
        'traceback': e.traceback,
        'method': e.method,
        'path': e.path,
        'status_code': e.status_code,
        'request_id': e.request_id,
        'user_agent': e.user_agent,
        'metadata': e.metadata or {},
    }


def build_report(
    *, days: int = 7, include_resolved: bool = False, limit: int = 50, fingerprint: str = ''
) -> dict:
    """The open groups of the last ``days`` days, or one group (``fingerprint``, any age)."""
    from django.conf import settings
    from django.db.models import Count, Max, Min
    from django.utils import timezone

    from core.errors.mode import state
    from core.errors.models import ErrorEvent
    from core.utils.site import site_base_url, store_name

    days = max(1, min(int(days), 90))
    limit = max(1, min(int(limit), 200))
    now = timezone.now()
    since = now - timedelta(days=days)
    events = ErrorEvent.objects.filter(created_at__gte=since)
    if fingerprint:
        events = ErrorEvent.objects.filter(fingerprint=fingerprint)
        include_resolved = True
    rows = list(
        events.values('fingerprint')
        .annotate(count=Count('id'), first_seen=Min('created_at'), last_seen=Max('created_at'))
        .order_by('-last_seen')[:_SCAN]
    )
    states = _states([r['fingerprint'] for r in rows])

    candidates = []
    for row in rows:
        st = status_of(states.get(row['fingerprint']), row['last_seen'])
        if st == 'resolved' and not include_resolved:
            continue
        latest = (
            ErrorEvent.objects.filter(fingerprint=row['fingerprint'])
            .order_by('-created_at')
            .first()
        )
        if latest is None:
            continue
        candidates.append((row, st, latest))
    candidates.sort(
        key=lambda c: (
            c[1] != 'regressed',
            _LEVEL_RANK.get(c[2].level, 3),
            -c[0]['count'],
            -c[0]['last_seen'].timestamp(),
        )
    )

    groups = []
    for row, st, latest in candidates[:limit]:
        paths = list(
            events.filter(fingerprint=row['fingerprint'])
            .exclude(path='')
            .values('path')
            .annotate(count=Count('id'))
            .order_by('-count')[:5]
        )
        decision = states.get(row['fingerprint'])
        groups.append(
            {
                'fingerprint': row['fingerprint'],
                'status': st,
                'resolved_at': decision.resolved_at.isoformat()
                if decision and decision.resolved_at
                else '',
                'level': latest.level,
                'kind': latest.kind,
                'source': (latest.metadata or {}).get('source', ''),
                'title': _title(latest),
                'count': row['count'],
                'first_seen': row['first_seen'].isoformat(),
                'last_seen': row['last_seen'].isoformat(),
                'paths': [{'path': p['path'], 'count': p['count']} for p in paths],
                'latest': _event(latest),
            }
        )

    mode = state()
    return {
        'store': store_name(),
        'site': site_base_url(),
        'version': getattr(settings, 'MORPHEUS_VERSION', ''),
        'generated_at': now.isoformat(),
        'days': days,
        'since': since.isoformat(),
        'detailed_capture': {
            'active': mode['active'],
            'until': mode['until'].isoformat() if mode['until'] else '',
        },
        'totals': {
            'events': events.count(),
            'groups_shown': len(groups),
            'errors': sum(1 for g in groups if g['level'] == 'error'),
            'warnings': sum(1 for g in groups if g['level'] == 'warning'),
        },
        'groups': groups,
    }


def _title(event) -> str:
    head = (event.message or '').strip().splitlines()[0] if event.message else ''
    cls = event.exception_class or event.level.title()
    if head.startswith(cls):
        return head[:160]
    return f'{cls}: {head}'[:160] if head else cls


def _context_line(ctx: dict) -> str:
    bits = []
    if ctx.get('method') or ctx.get('path'):
        bits.append(f'{ctx.get("method", "")} {ctx.get("path", "")}'.strip())
    if ctx.get('view'):
        bits.append(f'view `{ctx["view"]}`')
    if ctx.get('status'):
        bits.append(f'status {ctx["status"]}')
    if ctx.get('duration_ms'):
        bits.append(f'{ctx["duration_ms"]} ms')
    if ctx.get('query'):
        bits.append('query ' + ', '.join(f'{k}={v}' for k, v in ctx['query'].items()))
    if ctx.get('referer'):
        bits.append(f'from {ctx["referer"]}')
    if ctx.get('language'):
        bits.append(f'language {ctx["language"]}')
    if ctx.get('user_id'):
        bits.append('staff user' if ctx.get('is_staff') else 'signed-in shopper')
    if ctx.get('theme'):
        bits.append(f'theme {ctx["theme"]}')
    return '; '.join(bits)


def render_markdown(report: dict) -> str:
    """The report as Markdown, written to be pasted into Claude Code."""
    lines: list[str] = []
    store = report['store'] or report['site']
    lines.append(f'# Errors on {store} ({report["site"].rstrip("/")})')
    lines.append('')
    mode = report['detailed_capture']
    lines.append(
        f'Morpheus {report["version"]}. Report made {report["generated_at"][:16].replace("T", " ")} UTC, '
        f'covering the last {report["days"]} day(s). Detailed capture is '
        + (f'on until {mode["until"][:16].replace("T", " ")} UTC.' if mode['active'] else 'off.')
    )
    totals = report['totals']
    lines.append(
        f'{totals["groups_shown"]} open group(s): {totals["errors"]} error(s), '
        f'{totals["warnings"]} warning(s), from {totals["events"]} event(s) in the window.'
    )
    lines.append('')
    lines.append('## How to work through this')
    lines.append('')
    lines.append(
        '1. Reproduce each group from its request and context. Tracebacks name files '
        'and lines in the Morpheus repository (`/app/` is the repository root in the container).'
    )
    lines.append(
        '2. Find the root cause, fix it in the repository, and add a test that fails without the fix.'
    )
    lines.append(
        "3. Ship the fix as a release, then mark the group resolved: on the store's error log "
        'page, or `python manage.py errors_report --resolve <fingerprint>` in its web container. '
        'A resolved group that fires again reopens as regressed.'
    )
    if not report['groups']:
        lines.append('')
        lines.append('No open errors in this window.')
    for n, g in enumerate(report['groups'], 1):
        lines.extend(_render_group(n, g))
    lines.append('')
    return '\n'.join(lines)


def _render_group(n: int, g: dict) -> list[str]:
    """One group of the Markdown report."""
    lines: list[str] = []
    latest = g['latest']
    meta = latest.get('metadata') or {}
    lines.append('')
    lines.append(f'## {n}. [{g["level"]}] {g["title"]}')
    lines.append('')
    status = g['status'] + (
        f' (resolved {g["resolved_at"][:10]}, fired again since)'
        if g['status'] == 'regressed'
        else ''
    )
    lines.append(f'- Fingerprint: `{g["fingerprint"]}`, {status}')
    lines.append(
        f'- {g["count"]} event(s), first {g["first_seen"][:16].replace("T", " ")}, '
        f'last {g["last_seen"][:16].replace("T", " ")} UTC'
    )
    where = g['kind'] + (f' ({g["source"]})' if g['source'] else '')
    lines.append(f'- Where: {where}')
    if g['paths']:
        lines.append('- Paths: ' + ', '.join(f'`{p["path"]}` ({p["count"]})' for p in g['paths']))
    ctx = meta.get('context') or {}
    if ctx:
        lines.append(f'- Request: {_context_line(ctx)}')
    elif latest.get('method') or latest.get('path'):
        lines.append(f'- Request: {latest.get("method", "")} {latest.get("path", "")}'.rstrip())
    extra = {k: v for k, v in meta.items() if k not in ('context', 'source')}
    if extra:
        lines.append('- Details: ' + ', '.join(f'{k}={v}' for k, v in list(extra.items())[:12]))
    if latest.get('request_id'):
        lines.append(f'- Request id: `{latest["request_id"]}`')
    if latest.get('message'):
        lines.append('')
        lines.append('Message:')
        lines.append('```')
        lines.append(latest['message'][:2000])
        lines.append('```')
    if latest.get('traceback'):
        lines.append('')
        lines.append('Traceback (latest occurrence):')
        lines.append('```')
        lines.append(latest['traceback'][:12000].rstrip())
        lines.append('```')
    return lines


def resolve(fingerprint: str, *, user=None, note: str = '') -> bool:
    """Mark a group resolved. False when no event has that fingerprint."""
    from django.utils import timezone

    from core.errors.models import ErrorEvent, ErrorGroup

    if not ErrorEvent.objects.filter(fingerprint=fingerprint).exists():
        return False
    ErrorGroup.objects.update_or_create(
        fingerprint=fingerprint,
        defaults={
            'status': ErrorGroup.STATUS_RESOLVED,
            'resolved_at': timezone.now(),
            'resolved_by': user if getattr(user, 'is_authenticated', False) else None,
            'note': (note or '')[:2000],
        },
    )
    return True


#: A group with no event for this long is resolved by the nightly prune. The open list
#: then shows what is broken now: 113 of 141 groups on four stores were "open" weeks
#: after their last event (Oct 2026). If one comes back, it shows as regressed.
STALE_DAYS = 14


def resolve_stale(days: int = STALE_DAYS) -> int:
    """Resolve every unresolved group whose newest event is older than ``days``."""
    from datetime import timedelta

    from django.db.models import Max
    from django.utils import timezone

    from core.errors.models import ErrorEvent, ErrorGroup

    cutoff = timezone.now() - timedelta(days=days)
    resolved = set(
        ErrorGroup.objects.filter(status=ErrorGroup.STATUS_RESOLVED).values_list(
            'fingerprint', flat=True
        )
    )
    stale = [
        row['fingerprint']
        for row in ErrorEvent.objects.values('fingerprint').annotate(last=Max('created_at'))
        if row['last'] < cutoff and row['fingerprint'] not in resolved
    ]
    note = f'Resolved automatically: no new event for {days} days.'
    for fingerprint in stale:
        resolve(fingerprint, note=note)
    return len(stale)


def reopen(fingerprint: str) -> None:
    from core.errors.models import ErrorGroup

    ErrorGroup.objects.update_or_create(
        fingerprint=fingerprint,
        defaults={'status': ErrorGroup.STATUS_OPEN, 'resolved_at': None, 'resolved_by': None},
    )
