from django.contrib.auth import get_user_model
from django.test import TestCase


class AppsSurfaceSmoke(TestCase):
    def setUp(self):
        U = get_user_model()
        self.staff = U.objects.create_user(
            username='smoke_staff', email='smoke@example.com', password='x', is_staff=True,
            is_superuser=True,
        )
        self.client.force_login(self.staff)

    def test_all_three_surfaces_render(self):
        for url in ('/dashboard/apps/', '/dashboard/apps/store/', '/dashboard/updates/'):
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200, f'{url} -> {r.status_code}')

    def test_tab_strip_marks_the_current_view_active(self):
        installed = self.client.get('/dashboard/apps/').content.decode()
        browse = self.client.get('/dashboard/apps/store/').content.decode()
        self.assertIn('class="tab is-active">Installed', installed)
        self.assertIn('class="tab">Browse', installed)
        self.assertIn('class="tab is-active">Browse', browse)
        self.assertIn('class="tab">Installed', browse)

    def test_updates_no_longer_repeats_the_app_table(self):
        html = self.client.get('/dashboard/updates/').content.decode()
        self.assertNotIn('<th>Plugin</th>', html)
        self.assertIn('Manage apps', html)

    def test_system_apps_absent_from_the_catalogue(self):
        html = self.client.get('/dashboard/apps/').content.decode()
        self.assertNotIn('value="agent_core"', html)

    def test_merchant_wording_says_apps(self):
        html = self.client.get('/dashboard/apps/').content.decode()
        self.assertIn('Apps installed on this Morpheus instance', html)
        self.assertNotIn('Plugins installed on this Morpheus instance', html)
