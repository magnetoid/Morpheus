from django.db import migrations


class Migration(migrations.Migration):
    """The retired plugin ErrorEvent leaves Django's state; core.errors keeps the log.
    Their tables stay until v0.122.1, so v0.121.0 still runs if a store is put back
    (docs/plans/apps-consolidation-2026-10.md, Wave 1)."""

    dependencies = [('observability', '0002_delete_merchantmetric')]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.DeleteModel(name='ErrorEvent'),
            ],
        ),
    ]
