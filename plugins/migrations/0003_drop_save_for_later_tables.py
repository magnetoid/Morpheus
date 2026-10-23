"""save_for_later's tables (apps consolidation, Wave 2: wishlist ← save_for_later).

v0.123.0 took save_for_later out of the code and left its tables, so the release before
it still ran if a store was put back. Nothing has read them since. Each goes when it is
there and empty (core.migration_ops.DropLeftoverModel), and the app's django_migrations
row and switch go with them.
"""

from django.db import migrations

from core.migration_ops import forget_apps, leftover_table_drops


class Migration(migrations.Migration):
    dependencies = [('plugins', '0002_drop_removed_app_tables')]

    morpheus_contract = (
        'v0.123.0, the previous release, removed save_for_later and reads none of its tables.'
    )

    operations = [
        *leftover_table_drops(
            {
                'LeftoverSavedItem': 'save_for_later_saveditem',
                'LeftoverPriceSnapshot': 'save_for_later_pricesnapshot',
                'LeftoverSharedWishlist': 'save_for_later_sharedwishlist',
            }
        ),
        migrations.RunPython(forget_apps('save_for_later'), migrations.RunPython.noop),
    ]
