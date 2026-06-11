"""Template helpers for translations.

Usage:
    {% load morph_i18n %}
    <h1>{{ product|trans:"name" }}</h1>      ← uses request.LANGUAGE_CODE
    <p>{% trans_obj product "short_description" "es" %}</p>
"""

from __future__ import annotations

from django import template

register = template.Library()


@register.filter
def trans(obj, field: str):
    """{{ obj|trans:'field' }} — language from request.LANGUAGE_CODE."""
    if obj is None:
        return ''
    # Filter has no access to request; rely on a thread-local set by middleware,
    # else return the original value.
    from django.utils import translation as dj_trans

    from core.i18n.services import translated

    lang = (dj_trans.get_language() or '').split('-')[0]
    return translated(obj, field, lang)


@register.simple_tag
def trans_obj(obj, field: str, language_code: str = ''):
    """{% trans_obj product 'name' 'es' %} — explicit language."""
    if obj is None:
        return ''
    from core.i18n.services import translated

    return translated(obj, field, language_code)
