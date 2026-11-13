"""Data for the language bar: what to say, in each store language, to a visitor who prefers it.

The page is cached and the same for every visitor, so nothing here looks at the
visitor: the script decides in the browser whether to show the bar.
"""

from __future__ import annotations

from django import template
from django.templatetags.static import static
from django.utils import translation
from django.utils.translation import gettext

from core.i18n.services import language_name, store_languages

register = template.Library()


def bar_data() -> dict | None:
    """Each store language's own name and the three strings in it, or None when off."""
    from plugins.registry import app_registry  # noqa: PLC0415

    plugin = app_registry.get('localization')
    if plugin is None or not plugin.get_config_value('suggest_language', False):
        return None
    codes = store_languages()
    if len(codes) < 2:
        return None
    languages = {}
    for code in codes:
        with translation.override(code):
            languages[code] = {
                'name': language_name(code),
                # "{name}" is filled in by the script, not by a template.
                'also_in': gettext('This page is also in {name}.'),
                'switch': gettext('Switch'),
                'stay': gettext('Stay'),
            }
    # The script adds the stylesheet only when it shows the bar, so no page waits for it.
    return {'css': static('localization/language-bar.css'), 'languages': languages}


@register.simple_tag
def language_bar_data():
    return bar_data()
