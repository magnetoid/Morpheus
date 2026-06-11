from morpheus import Plugin


class AdminDashboardPlugin(Plugin):
    name = 'admin_dashboard'
    label = 'Admin Dashboard (shadcn/ui)'
    version = '1.0.0'
    description = 'Modern merchant dashboard built with Tailwind CSS and shadcn/ui components.'
    has_models = False

    def ready(self):
        # Register dashboard URLs under /dashboard/ prefix
        self.register_urls('plugins.installed.admin_dashboard.urls', prefix='dashboard/')

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
