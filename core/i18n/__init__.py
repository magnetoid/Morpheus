"""
core.i18n — translation kernel.

Generic-FK translation rows: one row per (object, language_code, field).
Any plugin can translate any model field without schema changes.

    from core.i18n import set_translation, get_translation, translated

    set_translation(product, 'name', 'es', 'La hora silenciosa')
    set_translation(product, 'short_description', 'es', '...')

    translated_name = translated(product, 'name', 'es')      # → 'La hora…' or original
    label = get_translation(product, 'name', 'es')           # → str | None

In templates:

    {% load morph_i18n %}
    <h1>{{ product|trans:'name' }}</h1>      ← uses request.LANGUAGE_CODE
"""

from __future__ import annotations

from core.i18n.services import (
    bulk_set_translations,
    get_translation,
    set_translation,
    translated,
    translations_for,
)

__all__ = [
    'bulk_set_translations',
    'get_translation',
    'set_translation',
    'translated',
    'translations_for',
]
