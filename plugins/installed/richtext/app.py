"""richtext — self-hosted vanilla Lexical editor, contributed as a plugin.

Owns the editor bundle (built once with esbuild from frontend/editor.js,
committed to static/richtext/), the {% richtext_field %} widget tag, and the
shared editor CSS. Replaces the CDN-loaded TipTap that used to live inline in
the product + CMS page forms. Disable this plugin and every richtext_field
degrades to a plain <textarea> (see templatetags/richtext.py).
"""

from __future__ import annotations

from morpheus.app import Plugin


class RichTextPlugin(Plugin):
    name = 'richtext'
    label = 'Rich Text Editor'
    version = '1.0.0'
    description = (
        'Self-hosted Lexical rich-text editor. Provides the '
        '{% richtext_field %} widget used by the product and CMS page forms. '
        'No CDN, no build step at deploy time (the bundle is committed).'
    )
    has_models = False
