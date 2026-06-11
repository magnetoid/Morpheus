"""`manage.py morpheus <subcommand>` — the public Morpheus CLI.

This is the framework's user-facing entry point. Subcommands::

    morpheus version
        Print the Morpheus version.

    morpheus list
        List installed plugins (active + inactive).

    morpheus new-plugin <name> [--label "..."] [--with-models] [--with-urls]
                              [--with-graphql] [--with-tasks]
        Scaffold a new plugin under plugins/installed/<name>/.

    morpheus new-theme <slug> [--label "..."]
        Scaffold a new storefront theme.

    morpheus enable <plugin>
    morpheus disable <plugin>
        Toggle a plugin's enabled state in the database.

    morpheus check
        Run Django's system check + a few Morpheus-specific
        invariants (active plugins, required metadata, leaked imports).

The dispatcher delegates to the legacy ``morph_create_*`` commands so
both spellings keep working.
"""

from __future__ import annotations

import argparse
import sys

from django.core.management import call_command, get_commands
from django.core.management.base import BaseCommand, CommandError

_HELP_BLURB = 'Morpheus framework CLI. Run `manage.py morpheus help` for the list of subcommands.'


class Command(BaseCommand):
    help = _HELP_BLURB

    def add_arguments(self, parser) -> None:
        parser.add_argument('subcommand', nargs='?', default='help')
        # REMAINDER lets us pass arbitrary flags through to the underlying
        # command (e.g. `morpheus new-plugin foo --with-urls`).
        parser.add_argument('extra', nargs=argparse.REMAINDER)

    def handle(self, *args, **opts) -> None:
        sub = opts['subcommand']
        rest = list(opts.get('extra') or [])

        dispatcher = {
            'help': self._help,
            'version': self._version,
            'list': self._list,
            'new-plugin': self._new_plugin,
            'new-theme': self._new_theme,
            'enable': self._enable,
            'disable': self._disable,
            'check': self._check,
        }
        fn = dispatcher.get(sub)
        if fn is None:
            self.stderr.write(self.style.ERROR(f'Unknown subcommand: {sub!r}'))
            self._help()
            sys.exit(2)
        fn(rest)

    # ── Subcommands ──────────────────────────────────────────────────────────

    def _help(self, _rest: list[str] | None = None) -> None:
        self.stdout.write('Morpheus CLI')
        self.stdout.write('')
        self.stdout.write('  morpheus version')
        self.stdout.write('  morpheus list')
        self.stdout.write(
            '  morpheus new-plugin <name> [--with-models] [--with-urls] [--with-graphql] [--with-tasks]'
        )
        self.stdout.write('  morpheus new-theme <slug> [--label "..."]')
        self.stdout.write('  morpheus enable <plugin>')
        self.stdout.write('  morpheus disable <plugin>')
        self.stdout.write('  morpheus check')

    def _version(self, _rest: list[str]) -> None:
        try:
            import morpheus  # type: ignore

            ver = getattr(morpheus, '__version__', '?')
        except Exception:  # noqa: BLE001
            ver = '?'
        self.stdout.write(f'Morpheus {ver}')

    def _list(self, _rest: list[str]) -> None:
        from plugins.registry import plugin_registry

        names = sorted(plugin_registry._classes.keys())
        if not names:
            self.stdout.write('No plugins discovered.')
            return
        for name in names:
            cls = plugin_registry._classes[name]
            active = plugin_registry.is_active(name)
            tag = self.style.SUCCESS('●') if active else self.style.WARNING('○')
            self.stdout.write(
                f'  {tag} {name:<24} {getattr(cls, "version", ""):<8} {getattr(cls, "label", "")}'
            )

    def _new_plugin(self, rest: list[str]) -> None:
        if 'morph_create_plugin' not in get_commands():
            raise CommandError('morph_create_plugin command not available.')
        if not rest:
            raise CommandError('usage: morpheus new-plugin <name> [flags...]')
        # call_command wants the bare argv after the command name.
        call_command('morph_create_plugin', *rest)

    def _new_theme(self, rest: list[str]) -> None:
        if 'morph_create_theme' not in get_commands():
            raise CommandError('morph_create_theme command not available.')
        if not rest:
            raise CommandError('usage: morpheus new-theme <slug> [flags...]')
        call_command('morph_create_theme', *rest)

    def _enable(self, rest: list[str]) -> None:
        self._toggle(rest, enabled=True)

    def _disable(self, rest: list[str]) -> None:
        self._toggle(rest, enabled=False)

    def _check(self, _rest: list[str]) -> None:
        """Run Django's system check + Morpheus-specific invariants."""
        from io import StringIO
        from pathlib import Path

        # 1. Django's stock system check.
        buf = StringIO()
        try:
            call_command('check', stdout=buf, stderr=buf)
            self.stdout.write(self.style.SUCCESS('✓ Django system check: clean'))
        except SystemExit:
            self.stderr.write(self.style.ERROR('✗ Django system check failed:'))
            self.stderr.write(buf.getvalue())
            sys.exit(1)

        # 2. Plugin metadata sanity.
        from plugins.registry import plugin_registry

        all_count = len(plugin_registry._classes)
        active_count = sum(1 for n in plugin_registry._classes if plugin_registry.is_active(n))
        self.stdout.write(self.style.SUCCESS(f'✓ Plugins: {active_count}/{all_count} active'))

        # 3. Leaked-import scan: every plugin.py should import from
        #    `morpheus`, not directly from the registry/contrib internals.
        leaks: list[str] = []
        installed = Path(__file__).resolve().parents[3] / 'plugins' / 'installed'
        for manifest in sorted(installed.glob('*/plugin.py')):
            text = manifest.read_text()
            if (
                'from plugins.base import' in text
                or 'from plugins.contributions import' in text
                or 'from core.hooks import MorpheusEvents' in text
            ):
                leaks.append(str(manifest.relative_to(installed.parent.parent)))
        if leaks:
            self.stdout.write(
                self.style.WARNING(f'⚠ {len(leaks)} plugin.py files still import from internals:')
            )
            for path in leaks:
                self.stdout.write(f'    {path}')
            self.stdout.write('  (run `morpheus check` after migrating to silence.)')
        else:
            self.stdout.write(
                self.style.SUCCESS('✓ Plugin manifests: all using `morpheus.*` imports')
            )

    def _toggle(self, rest: list[str], *, enabled: bool) -> None:
        if not rest:
            raise CommandError('usage: morpheus enable|disable <plugin>')
        name = rest[0]
        from plugins.models import PluginConfig
        from plugins.registry import plugin_registry

        if name not in plugin_registry._classes:
            raise CommandError(f'No such plugin: {name!r}')
        row, _ = PluginConfig.objects.get_or_create(plugin_name=name)
        row.is_enabled = enabled
        row.save(update_fields=['is_enabled', 'updated_at'])
        verb = 'Enabled' if enabled else 'Disabled'
        self.stdout.write(self.style.SUCCESS(f'{verb} plugin {name!r}.'))
        self.stdout.write('Restart the server for the change to take effect.')
