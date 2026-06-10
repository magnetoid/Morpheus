"""Built-in event names.

Re-export of `core.hooks.MorpheusEvents`'s constants as module-level
names so plugin code reads naturally::

    from morpheus import events
    self.register_hook(events.ORDER_PLACED, self.on_order)

This mirror is generated **dynamically** from `MorpheusEvents` — every
uppercase constant declared there is surfaced here automatically. It used
to be a hand-maintained list, which silently drifted: `PRODUCT_FORM_CARDS`
and `PRODUCT_FORM_SAVED` were added to `MorpheusEvents` but not here, so
`events.PRODUCT_FORM_CARDS` raised `AttributeError` inside the audiobooks
plugin's `ready()` and crashed its activation. Generating the names removes
that whole failure mode. `test_events_module_mirrors_registry` guards it.
"""

from __future__ import annotations

from core.hooks import MorpheusEvents as _E

# Surface every event constant declared on MorpheusEvents. Keeping this
# generated (not hand-listed) means a new event can never be missing here.
globals().update(
    {
        _name: _value
        for _name, _value in vars(_E).items()
        if _name.isupper() and not _name.startswith('_')
    }
)

__all__ = [name for name in list(globals()) if name.isupper() and not name.startswith('_')]
