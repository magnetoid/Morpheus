"""Janus's technical reports on Morpheus's own code (docs/plans/janus-core-brain-2026-10.md, C).

Janus files one with ``reports.file``. A superuser reviews it on AI → Reports and may
send it to the Morpheus project: sending opens GitHub's new-issue form, pre-filled, in
their own browser, and they submit it under their own account. The store holds no
token, and no report leaves without a person. A report is words, never code:
maintainers decide how core is patched.
"""

from __future__ import annotations

from urllib.parse import urlencode

MAX_TITLE = 200
MAX_AREA = 300
MAX_TEXT = 4000
# GitHub refuses a new-issue URL much past 8 KB; leave room for the title and encoding.
MAX_BODY = 5000


def _clean(text, limit: int) -> str:
    return str(text or '').strip()[:limit]


def file_report(*, title, problem, fix='', area='', user=None, conversation_key=''):
    """Record a report, or refresh the open one with the same title."""
    from django.conf import settings

    from core.assistant.models import CodeProposal

    title = ' '.join(_clean(title, MAX_TITLE).split())
    problem = _clean(problem, MAX_TEXT)
    if not title or not problem:
        raise ValueError('a report needs a title and a description of the problem')
    fields = {
        'area': _clean(area, MAX_AREA),
        'problem': problem,
        'fix': _clean(fix, MAX_TEXT),
        'morpheus_version': str(getattr(settings, 'MORPHEUS_VERSION', '') or '')[:32],
        'conversation_key': str(conversation_key or '')[:120],
        'reported_by': user if getattr(user, 'pk', None) else None,
    }
    report = CodeProposal.objects.filter(status='new', title__iexact=title).first()
    if report is None:
        return CodeProposal.objects.create(title=title, **fields)
    for name, value in fields.items():
        setattr(report, name, value)
    report.save()
    return report


def issue_body(report) -> str:
    """The issue text: the reviewed report, with emails, phones and IPs hashed."""
    from core.observability import scrub_pii

    parts = [
        '**Problem**',
        report.problem.strip(),
        '**Fix**',
        report.fix.strip() or 'Not fixed yet.',
    ]
    if report.area:
        parts.append(f'**Where:** {report.area}')
    if report.morpheus_version:
        parts.append(f'**Morpheus:** {report.morpheus_version}')
    parts.append('_Written by Janus on a Morpheus store and reviewed by its owner._')
    body = scrub_pii('\n\n'.join(parts))
    if len(body) > MAX_BODY:
        body = body[: MAX_BODY - 20].rstrip() + '\n\n… (shortened)'
    return body


def issue_url(report) -> str:
    """GitHub's new-issue form for this report, pre-filled."""
    from django.conf import settings

    from core.observability import scrub_pii

    query = urlencode({'title': scrub_pii(report.title), 'body': issue_body(report)})
    return f'{settings.MORPHEUS_REPORTS_URL}?{query}'


def mark_sent(report, user) -> None:
    from django.utils import timezone

    report.status = 'sent'
    report.sent_by = (getattr(user, 'email', '') or getattr(user, 'username', '') or '')[:200]
    report.sent_at = timezone.now()
    report.save(update_fields=['status', 'sent_by', 'sent_at', 'updated_at'])
