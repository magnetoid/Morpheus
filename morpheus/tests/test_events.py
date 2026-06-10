"""`morpheus.events` must mirror `core.hooks.MorpheusEvents` exactly.

This guards the failure mode that crashed audiobooks activation: an event
declared on MorpheusEvents but missing from the `morpheus.events` alias
makes `events.<NAME>` raise AttributeError inside a plugin's `ready()`.
"""

from __future__ import annotations

from django.test import SimpleTestCase

from core.hooks import MorpheusEvents
from morpheus import events


class EventsMirrorTests(SimpleTestCase):
    def test_events_module_mirrors_registry(self):
        declared = {
            name: value
            for name, value in vars(MorpheusEvents).items()
            if name.isupper() and not name.startswith('_')
        }
        missing = [name for name in declared if not hasattr(events, name)]
        self.assertEqual(
            missing,
            [],
            f'morpheus.events is missing event constants {missing} declared on '
            f'MorpheusEvents — they are generated, so this should never happen.',
        )
        for name, value in declared.items():
            self.assertEqual(getattr(events, name), value, f'{name} value mismatch')
