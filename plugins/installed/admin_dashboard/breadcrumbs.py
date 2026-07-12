"""Shared dashboard breadcrumb builder.

Every dashboard-contributing plugin built the same ``[Dashboard › Section › …]``
trail with its own copy of a ``_trail()`` helper — eight byte-near-identical
copies that differed only in the section's label and URL. This is the one
builder they call instead.

Owned by ``admin_dashboard`` because it renders the dashboard shell (the
``breadcrumb_trail`` view-context key + the ``_breadcrumb_trail.html`` partial);
a plugin's dashboard page only exists inside that shell, so depending on it for
the trail is honest, not new coupling.
"""

from __future__ import annotations


def build_trail(section_label: str, section_url: str, *items) -> list[dict]:
    """``[Dashboard › <section> › <items…>]`` for a view's ``breadcrumb_trail``.

    ``items`` are either ready-made ``{'label':…, 'url':…}`` dicts or plain
    strings (rendered as an unlinked leaf crumb).
    """
    trail = [
        {'label': 'Dashboard', 'url': '/dashboard/'},
        {'label': section_label, 'url': section_url},
    ]
    for item in items:
        trail.append(item if isinstance(item, dict) else {'label': str(item)})
    return trail
