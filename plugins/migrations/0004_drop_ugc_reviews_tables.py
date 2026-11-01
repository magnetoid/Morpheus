"""ugc_reviews' tables, and what is left of trust_signals and ugc_reviews (apps
consolidation, Wave 2: reviews <- trust_signals + ugc_reviews).

v0.129.0 took both apps out of the code and left ugc_reviews' tables, so the release
before it still ran if a store was put back. Nothing has read them since. Each goes when
it is there and empty (core.migration_ops.DropLeftoverModel); both apps' django_migrations
rows and switches go with them (trust_signals had no tables and no migrations).
"""

from django.db import migrations

from core.migration_ops import forget_apps, leftover_table_drops


class Migration(migrations.Migration):
    dependencies = [('plugins', '0003_drop_save_for_later_tables')]

    morpheus_contract = (
        'v0.129.0, the previous release, removed trust_signals and ugc_reviews and reads '
        'none of their tables, migration rows or switches.'
    )

    operations = [
        *leftover_table_drops(
            {
                'LeftoverReviewMedia': 'ugc_reviews_reviewmedia',
                'LeftoverCreatorInvite': 'ugc_reviews_creatorinvite',
            }
        ),
        migrations.RunPython(
            forget_apps('ugc_reviews', 'trust_signals'), migrations.RunPython.noop
        ),
    ]
