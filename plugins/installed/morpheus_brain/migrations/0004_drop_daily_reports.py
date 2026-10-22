from django.db import migrations, models


class Migration(migrations.Migration):
    """The DailyReport and ReportReference tables v0.122.0 left behind (docs/plans/apps-consolidation-2026-10.md)."""

    dependencies = [('morpheus_brain', '0003_forget_daily_reports')]

    morpheus_contract = (
        'v0.122.0, the previous release, took DailyReport and ReportReference out of the code.'
    )

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.CreateModel(
                    name='DailyReport',
                    fields=[('id', models.BigAutoField(primary_key=True))],
                    options={'db_table': 'morpheus_brain_dailyreport'},
                ),
                migrations.CreateModel(
                    name='ReportReference',
                    fields=[('id', models.BigAutoField(primary_key=True))],
                    options={'db_table': 'morpheus_brain_reportreference'},
                ),
            ],
        ),
        migrations.DeleteModel(name='ReportReference'),
        migrations.DeleteModel(name='DailyReport'),
    ]
