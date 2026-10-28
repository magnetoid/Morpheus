"""Linda's notification tools: the asking staff member's own inbox.

`notifications.list` is read-only and scope-less, like `help.*`: every staff
member has an inbox whatever their role. `notifications.update` hides or
changes notifications, which is what injected text would try with an urgent
alert, so it carries a write scope (out of the read-only modes) and
`requires_approval` (the merchant's own yes). Both refuse an external agent's
conversation: its user is the shared service account, not a person.
"""

from __future__ import annotations

from morpheus.core import ToolError, ToolResult, tool


def _person(context) -> object:
    from core.assistant import gates

    context = context or {}
    user = context.get('user')
    if gates.is_external_key(str(context.get('conversation_key') or '')) or not getattr(
        user, 'is_staff', False
    ):
        raise ToolError("notifications are read only from a staff member's own chat")
    return user


@tool(
    name='notifications.list',
    description=(
        "List the notifications in the asking staff member's own inbox (the dashboard "
        'bell): return requests, low and out-of-stock alerts, failed automatic tasks. '
        'Repeats of the same thing are one entry with a count. Filter by unread, '
        'level (info, warning, urgent) or kind; ask for snoozed or archived ones with show.'
    ),
    scopes=[],
    schema={
        'type': 'object',
        'properties': {
            'show': {
                'type': 'string',
                'enum': ['inbox', 'unread', 'snoozed', 'archived'],
                'description': 'Which notifications; default inbox.',
            },
            'level': {'type': 'string', 'enum': ['info', 'warning', 'urgent']},
            'kind': {'type': 'string', 'description': 'e.g. inventory.low_stock'},
            'limit': {'type': 'integer', 'description': 'At most this many (1-50, default 20).'},
        },
    },
)
def notifications_list_tool(
    *, show: str = 'inbox', level: str = '', kind: str = '', limit: int = 20, context=None
) -> ToolResult:
    from plugins.installed.notifications_center import services

    user = _person(context)
    qs = services.listing(user, show if show in ('unread', 'snoozed', 'archived') else 'inbox')
    if level:
        qs = qs.filter(level=level)
    if kind:
        qs = qs.filter(kind=kind)
    rows = [services.as_dict(n) for n in qs[: max(1, min(int(limit or 20), 50))]]
    counts = services.unread_counts(user)
    return ToolResult(
        output={'notifications': rows, **counts},
        display=f'{len(rows)} notifications, {counts["unread"]} unread.',
    )


@tool(
    name='notifications.update',
    description=(
        "Change one notification in the asking staff member's own inbox: read, unread, "
        'archive, unarchive, snooze (until: hour, tomorrow or week), wake, or mute / '
        'unmute its kind so they stop or start getting that kind. Take the id from '
        'notifications.list.'
    ),
    scopes=['system.write'],
    requires_approval=True,
    schema={
        'type': 'object',
        'properties': {
            'id': {'type': 'string', 'description': 'The notification id.'},
            'action': {
                'type': 'string',
                'enum': [
                    'read',
                    'unread',
                    'archive',
                    'unarchive',
                    'snooze',
                    'wake',
                    'mute',
                    'unmute',
                ],
            },
            'until': {'type': 'string', 'enum': ['hour', 'tomorrow', 'week']},
        },
        'required': ['id', 'action'],
    },
)
def notifications_update_tool(*, id: str, action: str, until: str = '', context=None) -> ToolResult:  # noqa: A002
    from plugins.installed.notifications_center import services

    user = _person(context)
    n = services.own(user, id)
    if n is None:
        raise ToolError('no such notification in your inbox')
    try:
        line = services.apply(n, action, until=until)
    except ValueError as e:
        raise ToolError(str(e)) from e
    return ToolResult(
        output={'ok': True, 'message': line, **services.unread_counts(user)}, display=line
    )
