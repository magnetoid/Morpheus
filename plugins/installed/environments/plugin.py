"""Environments plugin manifest."""

from __future__ import annotations

from morpheus.plugin import Plugin


class EnvironmentsPlugin(Plugin):
    name = 'environments'
    label = 'Environments'
    version = '0.1.0'
    description = 'Dev/staging/production environment management with snapshots and promotion.'
    has_models = True

    def ready(self) -> None:
        self.register_graphql_extension('plugins.installed.environments.graphql.queries')
