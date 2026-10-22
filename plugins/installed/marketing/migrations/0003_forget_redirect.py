from django.db import migrations


class Migration(migrations.Migration):
    """marketing.Redirect leaves Django's state; seo owns redirects, and nothing read this one.
    Their tables stay until v0.122.1, so v0.121.0 still runs if a store is put back
    (docs/plans/apps-consolidation-2026-10.md, Wave 1)."""

    dependencies = [('marketing', '0002_initial')]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.DeleteModel(name='Redirect'),
            ],
        ),
    ]
