"""
manage.py morph_import shopify --shop foo --token abc...
manage.py morph_import woocommerce --base-url https://shop.example --consumer-key ck_... --consumer-secret cs_...
"""

from __future__ import annotations

import json

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Import data from an external commerce platform.'

    def add_arguments(self, parser) -> None:
        parser.add_argument('source', choices=['shopify', 'woocommerce'])
        parser.add_argument('--shop', default='')
        parser.add_argument('--token', default='')
        parser.add_argument('--base-url', default='')
        parser.add_argument('--consumer-key', default='')
        parser.add_argument('--consumer-secret', default='')
        parser.add_argument(
            '--from-file', default='', help='Path to JSON fixture for offline imports.'
        )

    def handle(self, *args, **options) -> None:
        source = options['source']
        records = None
        if options['from_file']:
            with open(options['from_file']) as f:
                records = json.load(f)

        if source == 'shopify':
            from plugins.installed.importers.adapters.shopify import ShopifyImporter

            importer = ShopifyImporter(
                shop=options['shop'],
                token=options['token'],
                records=records,
            )
        else:
            from plugins.installed.importers.adapters.woocommerce import WooImporter

            importer = WooImporter(
                base_url=options['base_url'],
                consumer_key=options['consumer_key'],
                consumer_secret=options['consumer_secret'],
                records=records,
            )

        if not importer._client and not records:
            raise CommandError('Provide credentials, a custom client, or --from-file.')

        summary = importer.run(started_by='cli')
        self.stdout.write(self.style.SUCCESS(f'Imported: {summary.counts}'))
        if summary.errors:
            self.stdout.write(self.style.WARNING(f'Errors: {len(summary.errors)}'))
