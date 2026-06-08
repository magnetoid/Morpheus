"""Landing zone for Linda's gated, self-authored tool modules (ADR 0014, Phase 4).

A module arrives here ONLY through the apply engine (core/assistant/apply.py):
owner-approved → scanned → written to a selfdev/* branch → reviewed → merged →
deployed. ``load_generated_tools()`` imports every module here on boot so its
``@tool`` decorator runs. Wiring the registered tools into Linda's catalog is
Phase 7 — for now this just makes the landing zone real + self-loading.
"""

from __future__ import annotations

import contextlib
import importlib
import logging
import pkgutil

logger = logging.getLogger('morpheus.linda_generated')


def load_generated_tools() -> list[str]:
    """Import every non-underscore module in this package. Each import is
    best-effort — a broken generated module is logged, never fatal to boot."""
    loaded: list[str] = []
    for mod in pkgutil.iter_modules(__path__):
        if mod.name.startswith('_'):
            continue
        with contextlib.suppress(Exception):
            importlib.import_module(f'{__name__}.{mod.name}')
            loaded.append(mod.name)
    if loaded:
        logger.info('linda_generated: loaded %d generated tool module(s): %s', len(loaded), loaded)
    return loaded
