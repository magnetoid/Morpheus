from django.db import migrations, models


class Migration(migrations.Migration):
    """The wish list tables v0.122.0 left behind (docs/plans/apps-consolidation-2026-10.md)."""

    dependencies = [('customers', '0007_forget_wishlist')]

    morpheus_contract = (
        'v0.122.0, the previous release, took WishList and WishListItem out of the code.'
    )

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.CreateModel(
                    name='WishList',
                    fields=[('id', models.BigAutoField(primary_key=True))],
                    options={'db_table': 'customers_wishlist'},
                ),
                migrations.CreateModel(
                    name='WishListItem',
                    fields=[('id', models.BigAutoField(primary_key=True))],
                    options={'db_table': 'customers_wishlistitem'},
                ),
            ],
        ),
        migrations.DeleteModel(name='WishListItem'),
        migrations.DeleteModel(name='WishList'),
    ]
