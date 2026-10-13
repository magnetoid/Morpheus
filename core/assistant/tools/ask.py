"""``assistant.ask``: Linda asks the merchant a question, with buttons.

The chat renders the question under her answer with up to four choices and
"something else", and sends a click as the merchant's next message, marked as an
answer (``tool_name='answer'`` on the stored message). The choices are Linda's
words, so a clicked answer never approves a write (``gates.latest_human_turn``
reads it as empty): approving a change stays with the merchant's own words or the
Approve card, which shows the exact call the store refused.
"""

from __future__ import annotations

from core.assistant.tools.filesystem import ToolError, ToolResult, tool

_MAX_QUESTION = 300
_MAX_CHOICE = 80
_MAX_CHOICES = 4


@tool(
    name='assistant.ask',
    description=(
        'Ask the merchant a question before you go on, with up to four short choices '
        'shown as buttons (they can also type their own answer). Use it when the right '
        'next step depends on what they want: which products, which period, which of '
        'two approaches. After calling it, end your turn with the question in one short '
        'line; their answer arrives as their next message. Never use it to ask for '
        'approval of a change: when a change needs their yes, the store shows them '
        'Approve and Decline itself.'
    ),
    scopes=['system.read'],
    schema={
        'type': 'object',
        'properties': {
            'question': {'type': 'string', 'description': 'The question, one sentence.'},
            'choices': {
                'type': 'array',
                'items': {'type': 'string'},
                'description': 'Up to four short answers, a few words each. Optional.',
            },
        },
        'required': ['question'],
    },
)
def assistant_ask_tool(*, question: str, choices=None, agent=None, context=None) -> ToolResult:
    question = ' '.join(str(question or '').split())[:_MAX_QUESTION]
    if not question:
        raise ToolError('question is required')
    clean: list[str] = []
    for choice in choices if isinstance(choices, list) else []:
        text = ' '.join(str(choice or '').split())[:_MAX_CHOICE]
        if text and text not in clean:
            clean.append(text)
        if len(clean) == _MAX_CHOICES:
            break
    return ToolResult(
        output={
            'kind': 'question',
            'question': question,
            'choices': clean,
            'note': (
                "The question is on the merchant's screen with these choices. Now end your "
                'turn with the question in one short line and wait: their answer arrives '
                'as their next message.'
            ),
        }
    )
