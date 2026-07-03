"""{% richtext_field %} — the Lexical editor widget.

Active plugin → full editor markup enhanced by static/richtext/
lexical-editor.bundle.js. Inactive → a plain <textarea> (graceful
degradation; the field still submits). The bundle scans [data-richtext]
elements, so no per-page init script is needed.
"""

from __future__ import annotations

from django import template

register = template.Library()

# Toolbar buttons rendered in order. Each: (action, title, label_html).
# `headings` / `image` groups are filtered by the tag's flags.
_BASE_BUTTONS = [
    ('bold', 'Bold', '<b>B</b>'),
    ('italic', 'Italic', '<i>I</i>'),
    ('strike', 'Strikethrough', '<s>S</s>'),
    ('code', 'Inline code', '&lt;&gt;'),
    ('_divider', '', ''),
]
_HEADING_BUTTONS = [
    ('h2', 'Heading 2', 'H2'),
    ('h3', 'Heading 3', 'H3'),
    ('paragraph', 'Paragraph', '¶'),
    ('_divider', '', ''),
]
_LIST_BUTTONS = [
    ('bulletList', 'Bullet list', '•'),
    ('orderedList', 'Numbered list', '1.'),
    ('blockquote', 'Blockquote', '❝'),
    ('codeBlock', 'Code block', '≡'),
    ('hr', 'Divider', '―'),
    ('_divider', '', ''),
]
_LINK_BUTTONS = [
    ('link', 'Insert link', '🔗'),
    ('unlink', 'Remove link', 'Unlink'),
]
_IMAGE_BUTTON = ('image', 'Insert image (upload)', '🖼')
_TAIL_BUTTONS = [
    ('clear', 'Clear formatting', '⌫'),
    ('_divider', '', ''),
    ('undo', 'Undo', '↶'),
    ('redo', 'Redo', '↷'),
    ('_spacer', '', ''),
    ('source', 'Edit HTML source', 'HTML'),
]


def _toolbar(allow_headings: bool, allow_images: bool) -> list:
    buttons = list(_BASE_BUTTONS)
    if allow_headings:
        buttons += _HEADING_BUTTONS
    buttons += _LIST_BUTTONS + _LINK_BUTTONS
    if allow_images:
        buttons.append(_IMAGE_BUTTON)
    buttons += _TAIL_BUTTONS
    return buttons


@register.inclusion_tag('richtext/_field.html')
def richtext_field(
    *,
    name: str,
    value: str = '',
    id: str = '',  # noqa: A002 — template-facing kwarg name
    allow_headings: bool = True,
    allow_images: bool = False,
    expose_as: str = '',
    aria_label: str = 'Rich text editor',
):
    from plugins.registry import plugin_registry

    active = bool(plugin_registry.is_active('richtext'))
    return {
        'active': active,
        'name': name,
        'value': value or '',
        'field_id': id or name,
        'allow_headings': bool(allow_headings),
        'allow_images': bool(allow_images),
        'expose_as': expose_as,
        'aria_label': aria_label,
        'upload_url': '/dashboard/media/api/upload/',
        'toolbar': _toolbar(bool(allow_headings), bool(allow_images)),
    }
