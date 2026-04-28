"""Direct hook-registry access for code that runs outside `Plugin.ready()`.

Most of the time you should use ``self.register_hook(...)`` from inside
your plugin's ``ready()``. This module is the escape hatch when you
need to ``fire`` or ``filter`` an event from a service, view, or task.
"""
from __future__ import annotations

from core.hooks import hook_registry

__all__ = ['hook_registry', 'fire', 'filter_value']


def fire(event: str, **kwargs):
    """Fire an event. Returns the list of non-None handler return values."""
    return hook_registry.fire(event, **kwargs)


def filter_value(event: str, value, **kwargs):
    """Pipe `value` through every handler registered against `event`."""
    return hook_registry.filter(event, value=value, **kwargs)
