"""Janus activity log on the Linda activity dashboard.

The feed merges two sources Janus already writes:

* ``JanusLearning`` journal rows (``memories/daily/<date>.md``) — the line
  ``memory_tool`` appends for every memory change;
* ``AuditEvent`` rows under the ``janus.*`` slugs, written whenever a turn
  stores or forgets learned material.

Both live in the database, so the feed is the engine's own durable record
rather than anything reconstructed from container logs.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import Client, TestCase


def _staff():
    return get_user_model().objects.create_user(
        username='s', email='s@x.test', password='pw', is_staff=True
    )


class JanusActivityLogTests(TestCase):
    def setUp(self):
        self.c = Client()
        self.c.force_login(_staff())

    def _journal(self, day='2026-09-20', body=''):
        from core.assistant.models import JanusLearning

        return JanusLearning.objects.create(
            scope='',
            path=f'memories/daily/{day}.md',
            kind='journal',
            content=body,
        )

    def test_empty_state_renders(self):
        """No learning yet must not break the page."""
        r = self.c.get('/dashboard/agents/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Janus activity')
        self.assertContains(r, 'No Janus activity journalled yet')

    def test_journal_entries_appear_newest_first(self):
        self._journal(
            day='2026-09-19',
            body='- `09:15` **MEMORY** added: store sells only physical books\n',
        )
        self._journal(
            day='2026-09-20',
            body='- `14:02` **MEMORY** added: returns window is 14 days\n',
        )
        r = self.c.get('/dashboard/agents/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'returns window is 14 days')
        self.assertContains(r, 'store sells only physical books')
        # Newest day first.
        self.assertLess(
            r.content.index(b'returns window is 14 days'),
            r.content.index(b'store sells only physical books'),
        )

    def test_memory_line_is_parsed_into_clock_and_kind(self):
        self._journal(body='- `07:45` **MEMORY** updated: shipping is 3-5 days\n')
        r = self.c.get('/dashboard/agents/')
        self.assertContains(r, '07:45')
        self.assertContains(r, 'memory')

    def test_line_without_the_expected_shape_is_skipped(self):
        """A heading or stray text must not be shown as an event."""
        self._journal(
            body=(
                '# Daily memory journal\n\n'
                'some free prose that is not an entry\n'
                '- `08:00` **MEMORY** added: a real entry\n'
            )
        )
        r = self.c.get('/dashboard/agents/')
        self.assertContains(r, 'a real entry')
        self.assertNotContains(r, 'free prose that is not an entry')

    def test_audit_events_are_merged_in(self):
        from core.audit.models import AuditEvent

        AuditEvent.objects.create(
            event_type='janus.learned',
            actor_label='linda',
            target='janus',
            metadata={'paths': ['memories/MEMORY.md'], 'conversation': 'c1'},
        )
        r = self.c.get('/dashboard/agents/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'stored learning')
        self.assertContains(r, 'memories/MEMORY.md')

    def test_forgotten_learning_is_described(self):
        from core.audit.models import AuditEvent

        AuditEvent.objects.create(
            event_type='janus.learning_forgotten',
            actor_label='merchant',
            target='janus',
            metadata={'what': 'store note'},
        )
        r = self.c.get('/dashboard/agents/')
        self.assertContains(r, 'forgot store note')

    def test_helpers_never_raise_without_tables(self):
        """The view helpers swallow a broken read rather than 500 the page."""
        from plugins.installed.agent_core.views import _janus_activity_log

        out = _janus_activity_log()
        self.assertIn('events', out)
        self.assertIn('total', out)
        self.assertIn('active_days', out)
