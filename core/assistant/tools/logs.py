"""Log tools — search Sentry-mirrored ErrorEvent + recent stderr."""

from __future__ import annotations

from datetime import timedelta

from core.assistant.tools.filesystem import ToolError, ToolResult, tool


@tool(
    name='logs.recent_errors',
    description='Recent ErrorEvent rows from observability (last N hours).',
    scopes=['system.read'],
    schema={
        'type': 'object',
        'properties': {
            'hours': {'type': 'integer', 'minimum': 1, 'maximum': 168, 'default': 6},
            'limit': {'type': 'integer', 'minimum': 1, 'maximum': 100, 'default': 25},
        },
    },
)
def recent_errors_tool(*, hours: int = 6, limit: int = 25) -> ToolResult:
    from django.utils import timezone

    try:
        from plugins.installed.observability.models import ErrorEvent
    except Exception as e:  # noqa: BLE001
        return ToolResult(output={'errors': [], 'note': f'observability plugin unavailable: {e}'})
    since = timezone.now() - timedelta(hours=max(1, int(hours or 6)))
    rows = list(
        ErrorEvent.objects.filter(created_at__gte=since).order_by('-created_at')[
            : max(1, min(int(limit or 25), 100))
        ]
    )
    return ToolResult(
        output={
            'errors': [
                {
                    'when': e.created_at.isoformat(),
                    'source': e.source,
                    'message': (e.message or '')[:300],
                    'metadata': e.metadata or {},
                }
                for e in rows
            ],
            'window_hours': hours,
        },
        display=f'{len(rows)} error(s) in last {hours}h',
    )


@tool(
    name='logs.search',
    description='Search ErrorEvent.message for a substring.',
    scopes=['system.read'],
    schema={
        'type': 'object',
        'properties': {
            'query': {'type': 'string'},
            'limit': {'type': 'integer', 'minimum': 1, 'maximum': 50, 'default': 20},
        },
        'required': ['query'],
    },
)
def search_logs_tool(*, query: str, limit: int = 20) -> ToolResult:
    if not query.strip():
        raise ToolError('query required')
    try:
        from plugins.installed.observability.models import ErrorEvent
    except Exception as e:  # noqa: BLE001
        return ToolResult(output={'errors': [], 'note': f'unavailable: {e}'})
    rows = list(
        ErrorEvent.objects.filter(message__icontains=query).order_by('-created_at')[
            : max(1, min(int(limit or 20), 50))
        ]
    )
    return ToolResult(
        output={
            'query': query,
            'errors': [
                {
                    'when': e.created_at.isoformat(),
                    'source': e.source,
                    'message': (e.message or '')[:300],
                }
                for e in rows
            ],
        }
    )
