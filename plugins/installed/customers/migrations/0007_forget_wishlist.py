from django.db import migrations


class Migration(migrations.Migration):
    """WishList and WishListItem leave Django's state; nothing read or wrote them.
    Their tables stay until v0.122.1, so v0.121.0 still runs if a store is put back
    (docs/plans/apps-consolidation-2026-10.md, Wave 1)."""

    dependencies = [('customers', '0006_customersegment_segmentmigration')]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.DeleteModel(name='WishListItem'),
                migrations.DeleteModel(name='WishList'),
            ],
        ),
    ]
