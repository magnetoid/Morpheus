from django.db import migrations, models


class Migration(migrations.Migration):
    """The marketing_redirect table v0.122.0 left behind (docs/plans/apps-consolidation-2026-10.md)."""

    dependencies = [('marketing', '0003_forget_redirect')]

    morpheus_contract = 'v0.122.0, the previous release, took marketing.Redirect out of the code.'

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.CreateModel(
                    name='Redirect',
                    fields=[('id', models.BigAutoField(primary_key=True))],
                    options={'db_table': 'marketing_redirect'},
                ),
            ],
        ),
        migrations.DeleteModel(name='Redirect'),
    ]
