from django.db import migrations, models


class Migration(migrations.Migration):
    """The retired observability_errorevent table v0.122.0 left behind. Its stale rows
    (1,360 on dotbooks) go with it, on purpose: core.errors keeps the log (docs/plans/apps-consolidation-2026-10.md)."""

    dependencies = [('observability', '0003_forget_errorevent')]

    morpheus_contract = 'v0.122.0, the previous release, took the plugin ErrorEvent out of the code; core.errors keeps the log.'

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.CreateModel(
                    name='ErrorEvent',
                    fields=[('id', models.BigAutoField(primary_key=True))],
                    options={'db_table': 'observability_errorevent'},
                ),
            ],
        ),
        migrations.DeleteModel(name='ErrorEvent'),
    ]
