from django.db import migrations


class Migration(migrations.Migration):
    """Referral leaves Django's state; nothing created one.
    Their tables stay until v0.122.1, so v0.121.0 still runs if a store is put back
    (docs/plans/apps-consolidation-2026-10.md, Wave 1)."""

    dependencies = [('loyalty_points', '0003_loyaltytier_customerrfm_customertier_referral')]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.DeleteModel(name='Referral'),
            ],
        ),
    ]
