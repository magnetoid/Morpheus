"""RBAC plugin manifest."""

from __future__ import annotations

import logging

from morpheus.app import DashboardPage, Plugin, SettingsPanel
from morpheus.core import MorpheusEvents

logger = logging.getLogger('morpheus.rbac')


class RbacPlugin(Plugin):
    name = 'rbac'
    label = 'Roles & permissions'
    version = '1.0.0'
    description = (
        'Named roles + role bindings on Customer, optionally scoped per '
        'channel. Service: has_capability(user, cap). Six built-in role '
        'templates (admin, marketing_manager, inventory_manager, '
        'support_agent, analyst, content_editor).'
    )
    has_models = True

    def ready(self) -> None:
        # Bootstrap default roles after migrate runs at boot.
        try:
            from django.db import DatabaseError

            from plugins.installed.rbac.models import Role

            try:  # noqa: SIM105
                Role.ensure_system_roles()
            except DatabaseError:
                pass
        except Exception as e:  # noqa: BLE001
            logger.debug('rbac: ensure_system_roles deferred: %s', e)

        # Answer the platform's authorization question. core/authz.py fires
        # this and falls back to `is_staff` when nothing answers, so disabling
        # or removing rbac degrades to the pre-RBAC behaviour rather than
        # locking anyone out. Priority 50: this is the authority, not a filter
        # over someone else's answer.
        self.register_hook(MorpheusEvents.AUTHZ_CAPABILITY_CHECK, self.on_capability_check)

    def on_capability_check(self, value, *, user=None, capability='', channel=None, **_kw):
        """Resolve one capability from the user's role bindings.

        `value` is None until someone answers. Another subscriber having
        already granted it is respected (short-circuit) — this handler only
        ever *adds* an authority, it never revokes another's grant.
        """
        if value is True:
            return value
        from plugins.installed.rbac.services import has_capability

        try:
            return bool(has_capability(user, capability, channel=channel))
        except Exception:  # noqa: BLE001 — a lookup failure must not deny
            logger.warning('rbac: capability lookup failed for %s', capability, exc_info=True)
            return value

    def get_config_schema(self) -> dict:
        return {
            'type': 'object',
            'properties': {
                'enforcement_mode': {
                    'type': 'string',
                    'enum': ['off', 'log', 'enforce'],
                    'default': 'log',
                    'title': 'Enforcement',
                    'description': (
                        'How role capabilities are applied. '
                        '"Log only" (default) records what would be blocked without '
                        'blocking anything — start here, review Settings → Audit, then '
                        'switch to "Enforce". "Enforce" actually denies. "Off" skips the '
                        'check entirely. Owners/superusers always pass, so you cannot '
                        'lock yourself out.'
                    ),
                },
            },
        }

    def contribute_settings_panel(self):
        # No category on purpose → the 'Other apps' bucket. There is no
        # security/access settings category, and inventing one would mean
        # editing admin_dashboard's settings_categories.py on rbac's behalf —
        # a plugin reaching into a shell's file, which is the anti-pattern.
        # The roles UI itself is contributed as a DashboardPage below.
        return SettingsPanel(
            label='Roles & permissions',
            schema=self.get_config_schema(),
            category='team',
        )

    def contribute_agent_tools(self) -> list:
        from plugins.installed.rbac.agent_tools import (
            grant_role_tool,
            list_roles_tool,
            revoke_role_tool,
        )

        return [list_roles_tool, grant_role_tool, revoke_role_tool]

    def contribute_dashboard_pages(self) -> list:
        return [
            DashboardPage(
                label='Roles & users',
                slug='roles',
                view='plugins.installed.rbac.dashboard.roles_page',
                icon='shield-check',
                section='team',
                order=10,
                nav='settings',
                hint='Who can do what in the dashboard',
            ),
        ]
