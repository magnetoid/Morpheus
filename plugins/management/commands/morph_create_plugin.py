"""
manage.py morph_create_plugin <name>
    [--label "Display name"]
    [--description "..."]
    [--version 0.1.0]
    [--with-models]
    [--with-graphql]
    [--with-urls]
    [--with-tasks]
    [--target plugins/installed]

Generates a working Morpheus plugin scaffold and prints instructions to wire
it into settings.MORPHEUS_DEFAULT_PLUGINS (if not already there).
"""
from __future__ import annotations

import re
from pathlib import Path
from textwrap import dedent

from django.core.management.base import BaseCommand, CommandError

_NAME_RE = re.compile(r'^[a-z][a-z0-9_]*$')


class Command(BaseCommand):
    help = 'Scaffold a new Morpheus plugin in plugins/installed/'

    def add_arguments(self, parser) -> None:
        parser.add_argument('name', help='snake_case plugin name (must match directory).')
        parser.add_argument('--label', default='', help='Human-readable name. Defaults to Title Case of name.')
        parser.add_argument('--description', default='', help='One-line description.')
        parser.add_argument('--plugin-version', default='0.1.0', dest='plugin_version')
        parser.add_argument('--with-models', action='store_true')
        parser.add_argument('--with-graphql', action='store_true')
        parser.add_argument('--with-urls', action='store_true')
        parser.add_argument('--with-tasks', action='store_true')
        parser.add_argument(
            '--target',
            default='plugins/installed',
            help='Directory to create the plugin in.',
        )

    def handle(self, *args, **opts) -> None:
        name = opts['name']
        if not _NAME_RE.match(name):
            raise CommandError(
                f'Invalid plugin name {name!r}. Must be snake_case '
                '(letters, digits, underscores; start with a letter).'
            )

        target = Path(opts['target']) / name
        if target.exists():
            raise CommandError(f'{target} already exists.')

        label = opts['label'] or name.replace('_', ' ').title()
        version = opts['plugin_version']
        description = opts['description'] or f'{label} plugin.'

        files = self._build_files(
            name=name,
            label=label,
            version=version,
            description=description,
            with_models=opts['with_models'],
            with_graphql=opts['with_graphql'],
            with_urls=opts['with_urls'],
            with_tasks=opts['with_tasks'],
        )

        for rel_path, content in files.items():
            full = target / rel_path
            full.parent.mkdir(parents=True, exist_ok=True)
            full.write_text(content)
            self.stdout.write(self.style.SUCCESS(f'+ {full}'))

        path_str = str(target).replace('/', '.')
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('Plugin scaffolded.'))
        self.stdout.write('')
        self.stdout.write('Next steps:')
        self.stdout.write(f'  1. Add {path_str!r} to MORPHEUS_DEFAULT_PLUGINS in morph/settings.py')
        if opts['with_models']:
            self.stdout.write('  2. python manage.py makemigrations ' + name)
            self.stdout.write('  3. python manage.py migrate')
        else:
            self.stdout.write('  2. python manage.py check')
        self.stdout.write('  4. Read docs/PLUGIN_DEVELOPMENT.md or SKILLS.md for next moves.')

    # ── Templates ─────────────────────────────────────────────────────────────

    def _build_files(
        self, *, name: str, label: str, version: str, description: str,
        with_models: bool, with_graphql: bool, with_urls: bool, with_tasks: bool,
    ) -> dict[str, str]:
        cls_prefix = ''.join(part.capitalize() for part in name.split('_'))
        out: dict[str, str] = {}

        out['__init__.py'] = (
            f"default_app_config = 'plugins.installed.{name}.apps.{cls_prefix}Config'\n"
        )

        out['apps.py'] = dedent(f'''
            from django.apps import AppConfig


            class {cls_prefix}Config(AppConfig):
                name = 'plugins.installed.{name}'
                label = '{name}'
                default_auto_field = 'django.db.models.BigAutoField'
        ''').lstrip()

        plugin_body = self._plugin_py(
            cls_prefix=cls_prefix, name=name, label=label, version=version,
            description=description, with_models=with_models, with_graphql=with_graphql,
            with_urls=with_urls, with_tasks=with_tasks,
        )
        out['plugin.py'] = plugin_body

        out['tests/__init__.py'] = ''
        out['tests/test_smoke.py'] = self._smoke_test(name=name, cls_prefix=cls_prefix)

        if with_models:
            out['models.py'] = self._models_py(name=name)
            out['migrations/__init__.py'] = ''

        if with_graphql:
            out['graphql/__init__.py'] = ''
            out['graphql/queries.py'] = self._graphql_queries_py(cls_prefix=cls_prefix)

        if with_urls:
            out['urls.py'] = self._urls_py(name=name)
            out['views.py'] = self._views_py()

        if with_tasks:
            out['tasks.py'] = self._tasks_py(name=name)

        return out

    @staticmethod
    def _plugin_py(*, cls_prefix, name, label, version, description,
                   with_models, with_graphql, with_urls, with_tasks) -> str:
        ready_lines: list[str] = []
        if with_graphql:
            ready_lines.append(
                f"        self.register_graphql_extension('plugins.installed.{name}.graphql.queries')"
            )
        if with_urls:
            ready_lines.append(
                f"        self.register_urls('plugins.installed.{name}.urls', prefix='{name}/')"
            )
        if with_tasks:
            ready_lines.append(
                f"        self.register_celery_tasks('plugins.installed.{name}.tasks')"
            )
        if not ready_lines:
            ready_lines.append('        pass  # add register_* calls here')

        return dedent(f'''
            """{label} plugin manifest."""
            from __future__ import annotations

            from morpheus import Plugin, events


            class {cls_prefix}Plugin(Plugin):
                name = "{name}"
                label = "{label}"
                version = "{version}"
                description = {description!r}
                has_models = {str(with_models)}

                def ready(self) -> None:
            {chr(10).join(ready_lines)}

                # Example hook (uncomment when you wire it):
                # def ready(self) -> None:
                #     self.register_hook(events.ORDER_PLACED, self.on_order)
                #
                # def on_order(self, order, **kwargs):
                #     pass
        ''').lstrip()

    @staticmethod
    def _smoke_test(*, name, cls_prefix) -> str:
        return dedent(f'''
            """{name} plugin smoke test."""
            from __future__ import annotations

            from django.test import TestCase


            class {cls_prefix}SmokeTests(TestCase):
                def test_plugin_class_imports(self):
                    from plugins.installed.{name}.plugin import {cls_prefix}Plugin
                    self.assertEqual({cls_prefix}Plugin.name, "{name}")
        ''').lstrip()

    @staticmethod
    def _models_py(*, name) -> str:
        return dedent(f'''
            """{name} plugin — models."""
            from __future__ import annotations

            import uuid
            from morpheus import models


            class {name.capitalize()}Example(models.Model):
                id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
                name = models.CharField(max_length=200)
                created_at = models.DateTimeField(auto_now_add=True)

                class Meta:
                    ordering = ['-created_at']

                def __str__(self) -> str:
                    return self.name
        ''').lstrip()

    @staticmethod
    def _graphql_queries_py(*, cls_prefix) -> str:
        return dedent(f'''
            """GraphQL queries exposed by this plugin."""
            from __future__ import annotations

            import strawberry


            @strawberry.type
            class {cls_prefix}QueryExtension:

                @strawberry.field(description="Smoke field — replace with real query.")
                def {cls_prefix.lower()}_ping(self) -> str:
                    return "pong"
        ''').lstrip()

    @staticmethod
    def _urls_py(*, name) -> str:
        return dedent(f'''
            from django.urls import path
            from . import views

            app_name = "{name}"

            urlpatterns = [
                path("", views.index, name="index"),
            ]
        ''').lstrip()

    @staticmethod
    def _views_py() -> str:
        return dedent('''
            from morpheus.views import HttpResponse, render


            def index(request):
                return HttpResponse("Hello from a Morpheus plugin.")
        ''').lstrip()

    @staticmethod
    def _tasks_py(*, name) -> str:
        return dedent(f'''
            """{name} plugin — Celery tasks."""
            from __future__ import annotations

            import logging
            from celery import shared_task

            logger = logging.getLogger("morpheus.{name}")


            @shared_task(bind=True, time_limit=60, soft_time_limit=45)
            def example_task(self, payload: dict) -> None:
                logger.info("example_task received payload=%s", payload)
        ''').lstrip()
