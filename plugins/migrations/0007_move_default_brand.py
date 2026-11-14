"""The channel feeds' "Default brand" becomes one catalog setting (v0.163.0).

Google Shopping and the other channel apps each kept a `default_brand`; the
product page's structured data used none of them. Catalog now holds the one
store-wide fallback (`catalog/brand.py`), so the first brand a merchant typed
into a channel is copied there while catalog's is unset: Google Shopping's
first, then the other channels in a fixed order. The channels' stored rows are
left as they are, because the release before still reads them.
"""

from django.db import migrations

SOURCES = (
    'google_shopping',
    'meta_commerce',
    'pinterest_commerce',
    'tiktok_commerce',
    'snapchat_commerce',
    'microsoft_commerce',
    'openai_shopping',
)


def copy_default_brand(apps, schema_editor):
    config = apps.get_model('plugins', 'PluginConfig')
    catalog = config.objects.filter(plugin_name='catalog').first()
    held = catalog.config if catalog is not None and isinstance(catalog.config, dict) else {}
    if str(held.get('default_brand') or '').strip():
        return
    rows = {row.plugin_name: row for row in config.objects.filter(plugin_name__in=SOURCES)}
    for name in SOURCES:
        row = rows.get(name)
        stored = row.config if row is not None and isinstance(row.config, dict) else {}
        brand = str(stored.get('default_brand') or '').strip()
        if brand:
            catalog, _ = config.objects.get_or_create(plugin_name='catalog')
            current = catalog.config if isinstance(catalog.config, dict) else {}
            catalog.config = {**current, 'default_brand': brand}
            catalog.save(update_fields=['config', 'updated_at'])
            return


class Migration(migrations.Migration):
    dependencies = [('plugins', '0006_forget_wave2_payment_apps')]

    operations = [migrations.RunPython(copy_default_brand, migrations.RunPython.noop)]
