"""Agent tools over the error log: the same report Claude Code gets.

Read only, scope ``diagnostics.read`` (a hand-granted MCP scope; Janus holds it
in Developer mode). Resolving stays a human decision on the error log page or
``manage.py errors_report --resolve``.
"""

from __future__ import annotations

from core.agents import ToolError, ToolResult, tool


def _summary(group: dict) -> dict:
    latest = group['latest']
    return {
        'fingerprint': group['fingerprint'],
        'status': group['status'],
        'level': group['level'],
        'kind': group['kind'],
        'source': group['source'],
        'title': group['title'],
        'count': group['count'],
        'first_seen': group['first_seen'],
        'last_seen': group['last_seen'],
        'paths': group['paths'],
        'message': (latest.get('message') or '')[:500],
    }


@tool(
    name='errors.recent',
    description=(
        "The store's open error groups (crashes, error logs, failed jobs, browser errors, and "
        'while detailed capture is on: warnings, rejected requests, broken links, slow pages). '
        "Errors first, then by count. Use errors.get for one group's traceback and request."
    ),
    scopes=['diagnostics.read'],
    schema={
        'type': 'object',
        'properties': {
            'days': {'type': 'integer', 'description': 'Window in days, 1 to 90. Default 7.'},
            'limit': {'type': 'integer', 'description': 'Most groups, 1 to 50. Default 20.'},
            'include_resolved': {'type': 'boolean'},
        },
    },
)
def errors_recent_tool(
    *, days: int = 7, limit: int = 20, include_resolved: bool = False
) -> ToolResult:
    from core.errors.report import build_report

    report = build_report(
        days=days, include_resolved=include_resolved, limit=max(1, min(int(limit), 50))
    )
    groups = [_summary(g) for g in report['groups']]
    return ToolResult(
        output={
            'version': report['version'],
            'detailed_capture': report['detailed_capture'],
            'totals': report['totals'],
            'groups': groups,
        },
        display=f'{len(groups)} open error group(s) in the last {report["days"]} day(s)',
    )


@tool(
    name='errors.get',
    description=(
        'One error group by fingerprint: counts, paths, the latest message, full traceback and '
        'request context, as the error log page shows it.'
    ),
    scopes=['diagnostics.read'],
    schema={
        'type': 'object',
        'properties': {'fingerprint': {'type': 'string'}},
        'required': ['fingerprint'],
    },
)
def errors_get_tool(*, fingerprint: str) -> ToolResult:
    from core.errors.report import build_report

    fingerprint = (fingerprint or '').strip()[:64]
    report = build_report(fingerprint=fingerprint) if fingerprint else {'groups': []}
    if not report['groups']:
        raise ToolError(f'No error has the fingerprint {fingerprint!r}.')
    group = report['groups'][0]
    return ToolResult(output=group, display=group['title'])
