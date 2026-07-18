"""Seed the default legal/info CMS pages on deploy.

Idempotent: ``seed_legal_pages(force=False)`` skips slugs that already exist
(privacy/terms/imprint from the original manual seed) and creates the new ones
(cookies/accessibility/faq). Fail-soft — a content-seed hiccup must never wedge
the production ``migrate`` step; re-seed anytime with
``manage.py seed_legal_pages``.
"""

from django.db import migrations


def seed(apps, schema_editor):
    try:
        from plugins.installed.gdpr.services import seed_legal_pages

        seed_legal_pages(force=False)
    except Exception:  # noqa: BLE001
        import logging

        logging.getLogger('morpheus.gdpr').warning(
            'legal-page seed migration skipped (run manage.py seed_legal_pages)',
            exc_info=True,
        )


class Migration(migrations.Migration):

    dependencies = [
        ('gdpr', '0001_initial'),
        ('cms', '0008_insert_topics_mega_menu_item'),
    ]

    operations = [
        migrations.RunPython(seed, migrations.RunPython.noop),
    ]
