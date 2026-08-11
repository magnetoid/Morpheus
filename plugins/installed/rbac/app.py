"""RBAC plugin manifest."""

from __future__ import annotations

import logging

from morpheus.app import DashboardPage, Plugin

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
                section='access',
                order=10,
                nav='settings',
            ),
        ]
