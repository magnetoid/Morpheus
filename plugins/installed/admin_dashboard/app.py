from morpheus.app import Plugin
from morpheus.core import events


class AdminDashboardPlugin(Plugin):
    name = 'admin_dashboard'
    label = 'Admin Dashboard (shadcn/ui)'
    version = '1.0.0'
    description = 'Modern merchant dashboard built with Tailwind CSS and shadcn/ui components.'
    has_models = False

    def ready(self):
        # Register dashboard URLs under /dashboard/ prefix
        self.register_urls('plugins.installed.admin_dashboard.urls', prefix='dashboard/')
        # Surface "a new Morpheus version is available" (from the daily
        # core.tasks.check_for_updates cache) in the dashboard activity feed.
        self.register_hook(events.ACTIVITY_FEED, self.on_activity_feed, priority=95)
        # Contribution-taxonomy system check: a SettingsPanel with an unknown
        # category (or a DashboardPage with an unknown nav) renders nowhere —
        # fail `manage.py check` instead of hiding the surface silently.
        from plugins.installed.admin_dashboard import checks  # noqa: F401, PLC0415

    def on_activity_feed(self, value, limit=20, **kwargs):
        """Append an "Update available" item when the cached daily update check
        found the deployment behind upstream. No git/network here — reads cache."""
        from django.utils import timezone  # noqa: PLC0415

        from core.updates import cached_update_status  # noqa: PLC0415

        status = cached_update_status() or {}
        if status.get('available') == 'yes':
            behind = status.get('behind') or 0
            latest = status.get('latest') or ''
            value.append(
                {
                    'kind': 'update',
                    'icon': 'download',
                    'label': f'Morpheus update available — {latest}'.rstrip(' —'),
                    'hint': f'{behind} commit(s) behind upstream',
                    'url': '/dashboard/updates/',
                    'when': timezone.now(),
                }
            )
        return value

    def get_config_schema(self):
        return {
            'type': 'object',
            'properties': {
                'theme_mode': {
                    'type': 'string',
                    'enum': ['system', 'light', 'dark'],
                    'default': 'system',
                    'title': 'Default Theme',
                },
                'sidebar_collapsed': {'type': 'boolean', 'default': False},
            },
        }
