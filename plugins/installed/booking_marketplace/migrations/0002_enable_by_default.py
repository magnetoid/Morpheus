"""Enable the booking_marketplace plugin on deploy.

The plugin ships `enabled_by_default = False` (so a stock Morpheus install stays
a pure product store). For the Montenegro Experience deployment we always want
the experiences surface live, so this data migration upserts the PluginConfig
row to is_enabled=True. It runs during `migrate` (before gunicorn boots), so the
plugin registry sees it enabled on worker startup and wires /bookings/ + the
dashboard page.

Idempotent and reversible. An admin who later disables it in Dashboard -> Apps
is respected — this migration only sets the initial state once.
"""

from __future__ import annotations

from django.db import migrations

PLUGIN = 'booking_marketplace'


def enable(apps, schema_editor):
    PluginConfig = apps.get_model('plugins', 'PluginConfig')
    PluginConfig.objects.update_or_create(
        plugin_name=PLUGIN,
        defaults={'is_enabled': True},
    )


def disable(apps, schema_editor):
    PluginConfig = apps.get_model('plugins', 'PluginConfig')
    PluginConfig.objects.filter(plugin_name=PLUGIN).update(is_enabled=False)


class Migration(migrations.Migration):

    dependencies = [
        ('booking_marketplace', '0001_initial'),
        ('plugins', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(enable, disable),
    ]
