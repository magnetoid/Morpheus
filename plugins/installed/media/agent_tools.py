"""Media agent tools.

media.search was migrated here from core/assistant/tools/ecommerce.py so the
MediaAsset query lives in the plugin that owns it. Tool name + scope unchanged —
Linda sources it by name from the agent registry.
"""

from __future__ import annotations

from morpheus.core import ToolResult, tool


@tool(
    name='media.search',
    description=(
        'Search the media library. Filter by kind (image/video/audio/'
        'document/other), filename substring, or tag. Returns up to '
        '`limit` assets, newest first.'
    ),
    scopes=['system.read'],
    schema={
        'type': 'object',
        'properties': {
            'kind': {'type': 'string'},
            'filename': {'type': 'string'},
            'tag': {'type': 'string'},
            'limit': {'type': 'integer', 'minimum': 1, 'maximum': 50, 'default': 20},
        },
    },
)
def media_search_tool(
    *,
    kind: str = '',
    filename: str = '',
    tag: str = '',
    limit: int = 20,
) -> ToolResult:
    from plugins.installed.media.models import MediaAsset

    qs = MediaAsset.objects.all()
    if kind:
        qs = qs.filter(kind=kind)
    if filename:
        qs = qs.filter(filename__icontains=filename)
    if tag:
        qs = qs.filter(tags__contains=[tag])
    qs = qs.order_by('-created_at')[: max(1, min(int(limit or 20), 50))]
    rows = [
        {
            'id': str(a.id),
            'filename': a.filename,
            'kind': a.kind,
            'mime_type': a.mime_type,
            'size_bytes': a.size_bytes,
            'width': a.width,
            'height': a.height,
            'alt_text': a.alt_text,
            'tags': list(a.tags or []),
            'url': a.url,
        }
        for a in qs
    ]
    return ToolResult(output={'assets': rows, 'count': len(rows)}, display=f'{len(rows)} asset(s)')
