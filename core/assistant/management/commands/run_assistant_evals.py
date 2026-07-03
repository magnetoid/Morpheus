"""Score Linda against the golden eval tasks (core/assistant/evals/).

Runs each task through the real Assistant loop with the configured provider
and prints a pass/fail report + success rate. Use before/after prompt, skill,
or memory changes so regressions are caught by numbers, not vibes.
"""

from __future__ import annotations

import json

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Run the Linda golden-task evals and report the success rate.'

    def add_arguments(self, parser):
        parser.add_argument('--task', default='', help='Run a single task by name.')
        parser.add_argument('--json', action='store_true', help='Machine-readable output.')

    def handle(self, *args, **options):
        from core.assistant.evals import run_all
        from core.assistant.providers import get_default_provider

        provider = get_default_provider()
        if getattr(provider, 'name', '') in ('mock', 'unconfigured'):
            raise CommandError(
                'No AI provider configured — evals need a real provider. '
                'Set one in /dashboard/settings/ai/ or via env keys.'
            )

        results = run_all(only=options['task'])
        if not results:
            raise CommandError(f'no task named {options["task"]!r}')

        passed = sum(1 for r in results if r.ok)
        if options['json']:
            self.stdout.write(
                json.dumps(
                    {
                        'passed': passed,
                        'total': len(results),
                        'results': [
                            {
                                'name': r.name,
                                'ok': r.ok,
                                'failures': r.failures,
                                'tools_used': r.tools_used,
                                'duration_ms': r.duration_ms,
                            }
                            for r in results
                        ],
                    },
                    indent=2,
                )
            )
        else:
            for r in results:
                mark = self.style.SUCCESS('PASS') if r.ok else self.style.ERROR('FAIL')
                self.stdout.write(f'{mark}  {r.name}  ({r.duration_ms}ms)')
                for f in r.failures:
                    self.stdout.write(f'      - {f}')
            rate = passed / len(results)
            style = self.style.SUCCESS if rate >= 0.8 else self.style.WARNING
            self.stdout.write(style(f'\n{passed}/{len(results)} passed ({rate:.0%})'))
        if passed < len(results):
            raise SystemExit(1)
