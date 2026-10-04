"""Landing-page URLs for the enum-ish book fields (print type, language).

``/format/<value>/`` and ``/language/<value>/`` are matched by Django's ``slug``
converter and then filter books by the raw stored value, so a value can only be
served when it IS a slug. ``print_type`` has choices but, as a CharField, accepts
free text — one live book stored ``PDF report`` — and linking or sitemapping such
a value produced a URL that 404s. Every builder of these URLs goes through here.
"""

from __future__ import annotations

import re

_SLUG = re.compile(r'^[-a-zA-Z0-9_]+$')


def value_facet_url(prefix: str, value: str | None) -> str:
    """``/<prefix>/<value>/`` when the facet route can serve ``value``, else ``''``."""
    value = (value or '').strip()
    if not value or not _SLUG.match(value):
        return ''
    return f'/{prefix}/{value}/'
