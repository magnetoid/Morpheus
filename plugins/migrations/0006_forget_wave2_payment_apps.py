"""What is left of post_checkout_upsell, advanced_payments and fraud_rules (apps
consolidation, Wave 2: post_purchase <- post_checkout_upsell, payments <- advanced_payments
+ fraud_rules).

v0.132.0 took the three apps out of the code and copied their settings to post_purchase
and payments (0005), keeping their own rows so the release before still read them. Nothing
has read those rows since. None of the three had tables, and only advanced_payments had a
migrations package, with no migration in it, so this forgets their switches and settings.
"""

from django.db import migrations

from core.migration_ops import forget_apps


class Migration(migrations.Migration):
    dependencies = [('plugins', '0005_move_wave2_settings')]

    morpheus_contract = (
        'v0.132.0, the previous release, removed post_checkout_upsell, advanced_payments and '
        'fraud_rules and reads none of their migration rows or switches; their settings live '
        'on in post_purchase and payments.'
    )

    operations = [
        migrations.RunPython(
            forget_apps('post_checkout_upsell', 'advanced_payments', 'fraud_rules'),
            migrations.RunPython.noop,
        ),
    ]
