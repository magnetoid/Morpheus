"""janus app manifest — Settings → AI → Janus.

The merchant's controls for Janus, the engine behind Linda. The engine itself is
core (``core/assistant/janus_engine.py``) and reads these values through
``core/assistant/janus_settings.py``, so core never imports this app. This app
owns only the settings page and the config schema.
"""

from __future__ import annotations

from morpheus.app import Plugin
from plugins.contributions import DashboardPage


class JanusPlugin(Plugin):
    name = 'janus'
    label = 'Janus'
    version = '1.0.0'
    description = (
        'Settings for Janus, the engine behind Linda: switch Linda on or off, choose '
        'the model, cap tool steps and turn time, add standing instructions, toggle '
        'the bundled store skills, review what Linda has learned, and test the connection.'
    )
    has_models = False
    # The only place Linda can be switched back on or re-pinned to a provider.
    # Disabling the app would silently revert every setting to its default.
    protected = True
    # Surfaced as Settings → AI → Janus, not as an installable app.
    system = True

    def get_config_schema(self) -> dict:
        # `max_tool_turns` and `turn_timeout_s` deliberately carry no schema
        # default: an unset value must fall through to the engine's own default
        # (and LINDA_JANUS_TIMEOUT_S), not be pinned by this schema.
        return {
            'type': 'object',
            'properties': {
                'enabled': {'type': 'boolean', 'default': True},
                'model_source': {'type': 'string', 'enum': ['store', 'custom'], 'default': 'store'},
                'provider': {'type': 'string', 'default': ''},
                'model': {'type': 'string', 'default': ''},
                'base_url': {'type': 'string', 'default': ''},
                'api_key': {'type': 'string', 'format': 'password', 'default': ''},
                'max_tool_turns': {'type': 'integer', 'minimum': 1, 'maximum': 20},
                'turn_timeout_s': {'type': 'integer', 'minimum': 10, 'maximum': 170},
                'extra_instructions': {'type': 'string', 'default': ''},
                'bundled_skills': {'type': 'boolean', 'default': True},
                'learning': {'type': 'boolean', 'default': True},
                'reasoning_effort': {
                    'type': 'string',
                    'enum': ['low', 'medium', 'high'],
                    'default': 'low',
                },
            },
        }

    def contribute_dashboard_pages(self) -> list:
        return [
            DashboardPage(
                label='Janus',
                # Not 'settings': /dashboard/apps/<app>/settings/ is the legacy
                # settings-panel deep link and wins the route, so a page there
                # is unreachable.
                slug='engine',
                view='plugins.installed.janus.views.settings_view',
                icon='cpu',
                section='ai',
                order=15,
                nav='settings',
            ),
        ]
