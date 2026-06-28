"""Advisory briefing — model, generation degradation, and the Advisory tab."""

from django.contrib.auth import get_user_model
from django.test import TestCase

from plugins.installed.morpheus_brain.models import BrainBriefing
from plugins.installed.morpheus_brain.services import generate_briefing


class BriefingServiceTests(TestCase):
    def test_generate_degrades_without_provider(self):
        # No real AI provider in tests → mock/unconfigured. Must NOT crash and
        # must report not-configured rather than writing an empty briefing.
        result = generate_briefing()
        self.assertFalse(result.get('configured'))
        self.assertIn('message', result)
        self.assertEqual(BrainBriefing.objects.count(), 0)


class AdvisoryTabTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.staff = User.objects.create_user(
            username='boss', email='b@x.io', password='pw', is_staff=True
        )
        self.client.force_login(self.staff)

    def test_tab_present_and_empty_state(self):
        resp = self.client.get('/dashboard/apps/morpheus_brain/brain/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'data-tab="advisory"')
        self.assertContains(resp, 'Regenerate briefing')
        self.assertContains(resp, 'No briefing yet')

    def test_latest_briefing_renders_as_markdown(self):
        BrainBriefing.objects.create(
            title='Platform advisory — test',
            summary='All systems nominal.',
            content='## Health\n\nThings look **good** overall.',
            generated_by='mock · m1',
            tokens_used=321,
        )
        resp = self.client.get('/dashboard/apps/morpheus_brain/brain/')
        self.assertContains(resp, 'Platform advisory — test')
        # The core `md` filter rendered the markdown (heading + bold), not raw.
        self.assertContains(resp, '<h2>Health</h2>', html=False)
        self.assertContains(resp, '<strong>good</strong>', html=False)
        self.assertContains(resp, '321 tokens')

    def test_refresh_action_no_provider_warns_and_redirects(self):
        resp = self.client.post(
            '/dashboard/apps/morpheus_brain/brain/', {'action': 'refresh_briefing'}
        )
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(resp['Location'].endswith('#advisory'))
        self.assertEqual(BrainBriefing.objects.count(), 0)
