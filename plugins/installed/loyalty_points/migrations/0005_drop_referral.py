from django.db import migrations, models


class Migration(migrations.Migration):
    """The loyalty_referral table v0.122.0 left behind (docs/plans/apps-consolidation-2026-10.md)."""

    dependencies = [('loyalty_points', '0004_forget_referral')]

    morpheus_contract = (
        'v0.122.0, the previous release, took loyalty_points.Referral out of the code.'
    )

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.CreateModel(
                    name='Referral',
                    fields=[('id', models.BigAutoField(primary_key=True))],
                    options={'db_table': 'loyalty_referral'},
                ),
            ],
        ),
        migrations.DeleteModel(name='Referral'),
    ]
