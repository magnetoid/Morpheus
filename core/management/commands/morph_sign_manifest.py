"""Build and sign the release manifest that update clients read.

Publisher-side only. This runs where releases are built, never on a deployment
— the private key must not exist anywhere a customer's install can reach.

    # once, on the release machine
    python manage.py morph_sign_manifest --generate-key

    # each release
    MORPHEUS_SIGNING_KEY=… python manage.py morph_sign_manifest \
        --artifact https://morpheus.direct/dist/morpheus-0.43.2.tar.gz \
        --out stable.json

Then publish `stable.json` at the URL deployments point
`MORPHEUS_UPDATE_MANIFEST_URL` at, and ship the *public* key to them as
`MORPHEUS_UPDATE_PUBLIC_KEY`.
"""

from __future__ import annotations

import json
import os

from django.core.management.base import BaseCommand, CommandError


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
            # Per-app and per-theme entries go here once components have their
            # own channels; clients already read `core` only, so adding them is
            # backwards-compatible.
            'apps': {},
            'themes': {},
        }

        signed = sign_manifest(manifest, key)
        rendered = json.dumps(signed, indent=2, sort_keys=True)

        if opts['out']:
            with open(opts['out'], 'w', encoding='utf-8') as fh:
                fh.write(rendered + '\n')
            self.stdout.write(self.style.SUCCESS(f'Signed manifest for {version} → {opts["out"]}'))
        else:
            self.stdout.write(rendered)
