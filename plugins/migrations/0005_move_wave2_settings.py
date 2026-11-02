"""The settings of post_checkout_upsell, advanced_payments and fraud_rules move to the apps
that took their work over (apps consolidation, Wave 2: post_purchase <- post_checkout_upsell,
payments <- advanced_payments + fraud_rules).

v0.132.0 removed the three apps and kept their settings' keys. Each key they had stored is
copied to the new owner unless it already holds one (core.migration_ops.move_plugin_config):
without it, dotbooks' cash-on-delivery instructions would be blanked by the first save of the
payments settings or the next migrate. The old rows stay for the release before, which still
reads them, and go in the next release with forget_apps.
"""

from django.db import migrations

from core.migration_ops import move_plugin_config


class Migration(migrations.Migration):
    dependencies = [('plugins', '0004_drop_ugc_reviews_tables')]

    operations = [
        migrations.RunPython(
            move_plugin_config(
                (
                    'advanced_payments',
                    'payments',
                    ('cod_enabled', 'cod_instructions', 'test_enabled'),
                ),
                ('fraud_rules', 'payments', ('high_value_threshold',)),
                (
                    'post_checkout_upsell',
                    'post_purchase',
                    ('post_order_upsell_slug', 'post_order_copy'),
                ),
            ),
            migrations.RunPython.noop,
        ),
    ]
