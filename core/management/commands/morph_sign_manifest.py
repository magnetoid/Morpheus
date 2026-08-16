"""Build and sign the release manifest that update clients read.

Publisher-side only. This runs where releases are built, never on a deployment
— the private key must not exist anywhere a customer's install can reach.

    # once, on the release machine
    python manage.py morph_sign_manifest --generate-key

    # each release
    MORPHEUS_SIGNING_KEY=… python manage.py morph_sign_manifest \
        --artifact https://morpheus.direct/dist/morpheus-0.43.2.tar.gz \
        --sha256 … \
        --components components.json \
        --out stable.json

`components.json` carries the per-app / per-theme channel and looks like::

    {
      "apps":   {"my_app":   {"version": "1.4.0", "artifact": "https://…/my_app-1.4.0.tar.gz",
                              "sha256": "…", "min_core": "v0.44.0", "notes": "https://…"}},
      "themes": {"my_theme": {"version": "2.0.0", "artifact": "https://…", "sha256": "…"}}
    }

Every entry needs `version`, an https `artifact` and a 64-hex `sha256` — the
signature covers the checksum, which is what lets a client trust the bytes it
downloads. Then publish `stable.json` at the URL deployments point
`MORPHEUS_UPDATE_MANIFEST_URL` at, and ship the *public* key to them as
`MORPHEUS_UPDATE_PUBLIC_KEY`.
"""

from __future__ import annotations

import json
import os
import re

from django.core.management.base import BaseCommand, CommandError

_SHA256 = re.compile(r'^[0-9a-f]{64}$')
_NAME = re.compile(r'^[a-z][a-z0-9_]*$')


def load_components(path: str) -> dict:
    """Read + validate a components file. Raises CommandError with the exact
    entry at fault — a manifest with a malformed entry is worse than none,
    because clients would refuse it at apply time with a less useful message."""
    try:
        with open(path, encoding='utf-8') as fh:
            doc = json.load(fh)
    except (OSError, ValueError) as exc:
        raise CommandError(f'--components {path}: {exc}') from exc
    if not isinstance(doc, dict):
        raise CommandError('--components: top level must be an object')
    out: dict = {'apps': {}, 'themes': {}}
    for key in ('apps', 'themes'):
        entries = doc.get(key) or {}
        if not isinstance(entries, dict):
            raise CommandError(f'--components: {key!r} must be an object')
        for name, entry in entries.items():
            where = f'{key}.{name}'
            if not _NAME.match(str(name)):
                raise CommandError(f'--components: {where}: not a valid component name')
            if not isinstance(entry, dict):
                raise CommandError(f'--components: {where}: must be an object')
            version = str(entry.get('version') or '').strip()
            artifact = str(entry.get('artifact') or '').strip()
            sha256 = str(entry.get('sha256') or '').strip().lower()
            if not version:
                raise CommandError(f'--components: {where}: missing version')
            if not artifact.lower().startswith('https://'):
                raise CommandError(f'--components: {where}: artifact must be an https:// URL')
            if not _SHA256.match(sha256):
                raise CommandError(f'--components: {where}: sha256 must be 64 hex characters')
            out[key][str(name)] = {
                'version': version,
                'artifact': artifact,
                'sha256': sha256,
                'min_core': str(entry.get('min_core') or ''),
                'notes': str(entry.get('notes') or ''),
            }
    return out


class Command(BaseCommand):
    help = 'Build + Ed25519-sign the release manifest (publisher side).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--generate-key',
            action='store_true',
            help='Print a fresh keypair and exit. Store the private key securely.',
        )
        parser.add_argument('--artifact', default='', help='URL of the release tarball.')
        parser.add_argument('--sha256', default='', help='Checksum of the artifact.')
        parser.add_argument(
            '--min-upgrade-from',
            default='',
            help='Refuse upgrades from older than this (a gap the migrations cannot span).',
        )
        parser.add_argument(
            '--requires-rebuild',
            action='store_true',
            help='Set when this release changes dependencies — an in-place apply cannot pip install.',
        )
        parser.add_argument('--channel', default='stable')
        parser.add_argument(
            '--components',
            default='',
            help='JSON file with per-app / per-theme entries (see module docstring).',
        )
        parser.add_argument('--out', default='', help='Write here instead of stdout.')

    def handle(self, *args, **opts):
        from core.signing import generate_keypair, sign_manifest

        if opts['generate_key']:
            private, public = generate_keypair()
            self.stdout.write(self.style.WARNING('Store the PRIVATE key in your release secrets.'))
            self.stdout.write('It must never reach a deployment, an image, or this repository.\n')
            self.stdout.write(f'MORPHEUS_SIGNING_KEY={private}\n')
            self.stdout.write(self.style.SUCCESS('\nShip the PUBLIC key to deployments:'))
            self.stdout.write(f'MORPHEUS_UPDATE_PUBLIC_KEY={public}\n')
            return

        key = os.environ.get('MORPHEUS_SIGNING_KEY', '').strip()
        if not key:
            raise CommandError(
                'MORPHEUS_SIGNING_KEY is not set. Generate one with --generate-key, '
                'and keep it out of this repository.'
            )

        from django.conf import settings

        from core.versioning import component_versions

        data = component_versions() or {}
        version = str(getattr(settings, 'MORPHEUS_VERSION', '') or data.get('core') or '').strip()
        if not version:
            raise CommandError('Could not resolve MORPHEUS_VERSION.')

        components = (
            load_components(opts['components'])
            if opts.get('components')
            else {'apps': {}, 'themes': {}}
        )
        manifest = {
            'channel': opts['channel'],
            'core': {
                'version': version,
                'artifact': opts['artifact'],
                'sha256': opts['sha256'],
                'min_upgrade_from': opts['min_upgrade_from'],
                'requires_rebuild': bool(opts['requires_rebuild']),
                'notes': f'https://morpheus.direct/releases/{version}',
            },
            # The per-app / per-theme channel. Clients that predate it read
            # `core` only, so an empty or populated map is equally safe for them.
            'apps': components['apps'],
            'themes': components['themes'],
        }

        signed = sign_manifest(manifest, key)
        rendered = json.dumps(signed, indent=2, sort_keys=True)

        if opts['out']:
            with open(opts['out'], 'w', encoding='utf-8') as fh:
                fh.write(rendered + '\n')
            self.stdout.write(self.style.SUCCESS(f'Signed manifest for {version} → {opts["out"]}'))
        else:
            self.stdout.write(rendered)
