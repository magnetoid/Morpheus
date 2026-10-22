"""The tables of the apps v0.122.0 removed (apps consolidation, Wave 1).

v0.122.0 took the code out and left the tables, so the release before it still ran
if a store was put back. Nothing has read them since. Each one goes when it is there
and empty (core.migration_ops.DropLeftoverModel). The rows django_migrations and
PluginConfig kept for those apps go too.
"""

from django.db import migrations, models

from core.migration_ops import DropLeftoverModel

#: name in this migration's state → the table v0.122.0 left behind; children first.
LEFTOVERS = {
    'LeftoverOneClickToken': 'one_click_oneclicktoken',
    'LeftoverChannelPreference': 'rich_post_purchase_channelpreference',
    'LeftoverCarrierEmission': 'smart_shipping_carrieremission',
    'LeftoverOrderShipment': 'smart_shipping_ordershipment',
    'LeftoverReferral': 'referrals_referral',
    'LeftoverReferralCode': 'referrals_referralcode',
    'LeftoverAssignment': 'experiment_assignment',
    'LeftoverExposure': 'experiment_exposure',
    'LeftoverExperiment': 'experiment',
    'LeftoverFunctionInvocation': 'functions_functioninvocation',
    'LeftoverFunction': 'functions_function',
    'LeftoverDeployment': 'environments_deployment',
    'LeftoverEnvironmentSnapshot': 'environments_environmentsnapshot',
    'LeftoverEnvironment': 'environments_environment',
    'LeftoverBlock': 'journal_block',
    'LeftoverPost': 'journal_post',
    'LeftoverAsset': 'brand_kit_asset',
    'LeftoverDesignTokenSet': 'brand_kit_designtokenset',
}
REMOVED_APPS = (
    'brand_kit',
    'environments',
    'experiments',
    'functions',
    'journal',
    'lumina',
    'one_click',
    'referrals',
    'rich_post_purchase',
    'smart_shipping',
)


def forget_the_removed_apps(apps, schema_editor):
    """Their django_migrations rows, so an app given one of these names later starts
    from 0001, and their switch rows, which the Apps catalogue no longer lists."""
    from django.db.migrations.recorder import MigrationRecorder

    MigrationRecorder(schema_editor.connection).migration_qs.filter(app__in=REMOVED_APPS).delete()
    apps.get_model('plugins', 'PluginConfig').objects.filter(plugin_name__in=REMOVED_APPS).delete()


class Migration(migrations.Migration):
    dependencies = [('plugins', '0001_initial')]

    morpheus_contract = (
        'v0.122.0, the previous release, removed these apps and reads none of their tables.'
    )

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.CreateModel(
                    name=name,
                    fields=[('id', models.BigAutoField(primary_key=True))],
                    options={'db_table': table},
                )
                for name, table in LEFTOVERS.items()
            ],
        ),
        *[DropLeftoverModel(name=name) for name in LEFTOVERS],
        migrations.RunPython(forget_the_removed_apps, migrations.RunPython.noop),
    ]
