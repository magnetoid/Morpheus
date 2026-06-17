"""Linda memory editor — RBAC + CRUD.

Read is staff-only; create/edit/delete are superuser-only (editing Linda's
remembered facts changes how she behaves).
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import Client, TestCase

LIST_URL = '/dashboard/agents/memory/'
ACTION_URL = '/dashboard/agents/memory/action/'


def _memory(**kw):
    from core.assistant.models import LindaMemory

    defaults = {'scope': 'merchant', 'key': 'prefers_audiobooks', 'value': 'yes', 'source': 'seed'}
    defaults.update(kw)
    return LindaMemory.objects.create(**defaults)


class MemoryDashboardRbacTests(TestCase):
    def setUp(self):
        U = get_user_model()
        self.staff = U.objects.create_user(
            username='staff', email='s@x.test', password='pw', is_staff=True
        )
        self.owner = U.objects.create_user(
            username='owner', email='o@x.test', password='pw', is_staff=True, is_superuser=True
        )
        self.m = _memory()

    # ── Read: staff-only ────────────────────────────────────────────────────
    def test_list_redirects_anonymous(self):
        self.assertEqual(Client().get(LIST_URL).status_code, 302)

    def test_list_renders_for_staff(self):
        c = Client()
        c.force_login(self.staff)
        r = c.get(LIST_URL)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'prefers_audiobooks')

    # ── Mutations: superuser-only ───────────────────────────────────────────
    def test_create_forbidden_for_non_superuser(self):
        from core.assistant.models import LindaMemory

        c = Client()
        c.force_login(self.staff)
        r = c.post(
            ACTION_URL, {'action': 'create', 'scope': 'merchant', 'key': 'k2', 'value': 'v2'}
        )
        self.assertEqual(r.status_code, 403)
        self.assertFalse(LindaMemory.objects.filter(key='k2').exists())

    def test_delete_forbidden_for_non_superuser(self):
        from core.assistant.models import LindaMemory

        c = Client()
        c.force_login(self.staff)
        r = c.post(ACTION_URL, {'action': 'delete', 'memory_id': str(self.m.id)})
        self.assertEqual(r.status_code, 403)
        self.assertTrue(LindaMemory.objects.filter(id=self.m.id).exists())

    # ── Superuser CRUD ──────────────────────────────────────────────────────
    def test_superuser_create(self):
        from core.assistant.models import LindaMemory

        c = Client()
        c.force_login(self.owner)
        r = c.post(
            ACTION_URL,
            {'action': 'create', 'scope': 'seasonal', 'key': 'summer_sale', 'value': '20% off'},
        )
        self.assertEqual(r.status_code, 302)
        m = LindaMemory.objects.get(key='summer_sale')
        self.assertEqual(m.scope, 'seasonal')
        self.assertEqual(m.value, '20% off')

    def test_superuser_edit_updates_value(self):
        from core.assistant.models import LindaMemory

        c = Client()
        c.force_login(self.owner)
        r = c.post(
            ACTION_URL,
            {'action': 'edit', 'scope': self.m.scope, 'key': self.m.key, 'value': 'changed'},
        )
        self.assertEqual(r.status_code, 302)
        self.m.refresh_from_db()
        self.assertEqual(self.m.value, 'changed')
        self.assertEqual(LindaMemory.objects.filter(key=self.m.key).count(), 1)  # no dup row

    def test_superuser_delete(self):
        from core.assistant.models import LindaMemory

        c = Client()
        c.force_login(self.owner)
        r = c.post(ACTION_URL, {'action': 'delete', 'memory_id': str(self.m.id)})
        self.assertEqual(r.status_code, 302)
        self.assertFalse(LindaMemory.objects.filter(id=self.m.id).exists())

    def test_invalid_create_is_rejected_cleanly(self):
        from core.assistant.models import LindaMemory

        c = Client()
        c.force_login(self.owner)
        before = LindaMemory.objects.count()
        r = c.post(ACTION_URL, {'action': 'create', 'scope': 'merchant', 'key': '', 'value': ''})
        self.assertEqual(r.status_code, 302)  # redirects back with an error message
        self.assertEqual(LindaMemory.objects.count(), before)  # nothing created
