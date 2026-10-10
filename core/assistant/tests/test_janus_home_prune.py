"""Conversation homes nobody has used for a week are removed.

Each chat has its own Janus home under the conversation root, so with chats the
number of homes grows with every new chat instead of staying one per staff
member. Nothing in a home has to survive: what Janus learns is harvested into
the database after every turn, and a chat reopened without its home starts a
fresh Janus session that gets the recap from the stored messages.
"""

from __future__ import annotations

import os
import tempfile
import time
from pathlib import Path

from django.test import SimpleTestCase

from core.assistant import janus_engine

_WEEK = 7 * 24 * 3600


def _home(root: Path, name: str, age_s: float) -> Path:
    home = root / name
    home.mkdir()
    (home / 'state.db').write_text('x')
    stamp = time.time() - age_s
    for path in (home / 'state.db', home):
        os.utime(path, (stamp, stamp))
    return home


class PruneIdleHomesTests(SimpleTestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())

    def test_only_homes_idle_for_a_week_go(self):
        stale = _home(self.root, 'linda-aaaaaaaaaaaa', _WEEK + 3600)
        fresh = _home(self.root, 'linda-bbbbbbbbbbbb', 3600)
        removed = janus_engine.prune_idle_homes(self.root, keep=self.root / 'linda-cccccccccccc')
        self.assertEqual(removed, 1)
        self.assertFalse(stale.exists())
        self.assertTrue(fresh.exists())

    def test_the_home_in_use_and_foreign_directories_stay(self):
        current = _home(self.root, 'linda-dddddddddddd', _WEEK * 2)
        foreign = _home(self.root, 'not-a-home', _WEEK * 2)
        janus_engine.prune_idle_homes(self.root, keep=current)
        self.assertTrue(current.exists())
        self.assertTrue(foreign.exists())
