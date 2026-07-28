"""Theme SDK — authoring a Morpheus storefront theme.

One of the three project SDKs (torsor ADR 0035 /
``docs/plans/sdk-restructure-2026-07.md``). A theme declares named slots and
renders plugin-contributed blocks; plugins fill slots with ``StorefrontBlock``.

Python surface is intentionally thin — themes are template-driven::

    from morpheus.theme import StorefrontBlock

Templates use the ``{% load morph %}`` tag library (``storefront_blocks``,
``plugin_enabled``, ``money``, ``ai_disclosure``, …) — see
``core/templatetags/morph.py``. The slot contract + theme manifest live under
``themes/library/<name>/``. (Slot registry + manifest helpers are surfaced here
as the Theme SDK matures — see the migration plan, step 4.)
"""

from __future__ import annotations

from plugins.contributions import StorefrontBlock

__all__ = ['StorefrontBlock']
