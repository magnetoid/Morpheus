"""``reports.file``: Janus records a defect it found in Morpheus's own code.

The report waits on AI → Reports until a superuser sends it to the Morpheus project
or dismisses it (core/assistant/reports.py). Filing changes nothing in the store and
sends nothing anywhere, so it needs no yes from the merchant
(``agent_mcp/linda_turn._NO_CONSENT``); its write scope keeps it out of run_python's
read-only sandbox and out of the read-only chat modes.
"""

from __future__ import annotations

from core.assistant.tools.filesystem import ToolError, ToolResult, tool


@tool(
    name='reports.file',
    description=(
        "Record a defect you found in Morpheus itself (the platform's code, not this "
        "store's data or settings) for the store owner to review and send to the "
        'Morpheus team. Describe it in words: what is wrong, where, and how it was or '
        'could be fixed. Never include code, secrets or customer data. Nothing is sent '
        'until the owner sends it.'
    ),
    scopes=['system.write'],
    schema={
        'type': 'object',
        'properties': {
            'title': {'type': 'string', 'description': 'One line naming the defect.'},
            'problem': {
                'type': 'string',
                'description': 'What goes wrong, when, and how you found it.',
            },
            'fix': {
                'type': 'string',
                'description': 'How it was fixed or could be fixed, in words. Optional.',
            },
            'area': {
                'type': 'string',
                'description': 'Where it lives: a module, file or dashboard page. Optional.',
            },
        },
        'required': ['title', 'problem'],
    },
)
def reports_file_tool(
    *, title: str, problem: str, fix: str = '', area: str = '', agent=None, context=None
) -> ToolResult:
    from core.assistant import gates, reports

    context = context or {}
    key = str(context.get('conversation_key') or '')
    user = context.get('user')
    # An external agent's message is not the store's: it never files in the owner's queue.
    if gates.is_external_key(key) or not getattr(user, 'is_staff', False):
        raise ToolError("reports are filed only from a merchant's own chat")
    try:
        report = reports.file_report(
            title=title, problem=problem, fix=fix, area=area, user=user, conversation_key=key
        )
    except ValueError as e:
        raise ToolError(str(e)) from e
    return ToolResult(
        output={
            'filed': True,
            'id': str(report.id),
            'note': (
                'Recorded. The store owner reviews it on AI → Reports and decides '
                'whether to send it to the Morpheus team.'
            ),
        }
    )
