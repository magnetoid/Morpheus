from django.db import migrations


class Migration(migrations.Migration):
    """DailyReport and ReportReference leave Django's state; nothing created them.
    Their tables stay until v0.122.1, so v0.121.0 still runs if a store is put back
    (docs/plans/apps-consolidation-2026-10.md, Wave 1)."""

    dependencies = [('morpheus_brain', '0002_brainbriefing')]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.DeleteModel(name='ReportReference'),
                migrations.DeleteModel(name='DailyReport'),
            ],
        ),
    ]
