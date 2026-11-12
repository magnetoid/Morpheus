"""Linda's tool for AI drafts of translations (the reading and approving tools are core.i18n's)."""

# ruff: noqa: PLC0415 — model imports are lazy (load-order safe).
from __future__ import annotations

from core.agents import ToolError, ToolResult, tool


@tool(
    name='i18n.draft_translations',
    description=(
        'Ask the AI to draft translations of up to 50 objects of one kind into one '
        'language: the ids given, else the ones with no translation yet. Drafts are '
        'never shown to shoppers until the merchant reviews them (i18n.approve_translation '
        'or the Translations page). Kinds come from i18n.translation_status.'
    ),
    scopes=['i18n.write'],
    requires_approval=True,
    schema={
        'type': 'object',
        'properties': {
            'kind': {'type': 'string', 'description': "e.g. 'catalog.product'"},
            'language_code': {'type': 'string', 'description': "e.g. 'sr'"},
            'object_ids': {
                'type': 'array',
                'items': {'type': 'string'},
                'description': 'At most 50; leave out to draft the missing ones.',
            },
        },
        'required': ['kind', 'language_code'],
    },
)
def draft_translations_tool(*, kind: str, language_code: str, object_ids=None) -> ToolResult:
    from plugins.installed.localization.drafting import BATCH_LIMIT, DraftError, queue_drafts

    ids = [str(pk) for pk in (object_ids or [])]
    if len(ids) > BATCH_LIMIT:
        raise ToolError(f'At most {BATCH_LIMIT} objects at a time.')
    try:
        result = queue_drafts(kind, (language_code or '').lower(), ids)
    except DraftError as e:
        raise ToolError(str(e)) from e
    return ToolResult(
        output={'kind': kind, 'language': language_code, **result},
        display=(
            f'Queued {result["queued"]} AI draft(s) of {kind} in {language_code}; '
            'they wait for review before shoppers see them'
            if result['queued']
            else 'Nothing to draft: every object has a translation or a draft.'
        ),
    )
