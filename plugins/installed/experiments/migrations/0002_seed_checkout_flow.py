"""Seed the checkout_flow A/B experiment in `draft` status.

The experiment lives at /dashboard/system/self-improvement/... once
an admin promotes it to `running`. Until then it has no exposures
and variant_for() returns the control. Idempotent — re-running the
migration does not duplicate.
"""

from django.db import migrations


def seed(apps, schema_editor):
    Experiment = apps.get_model('experiments', 'Experiment')
    Experiment.objects.get_or_create(
        key='checkout_flow',
        defaults={
            'name': 'Checkout flow: 3-step vs one-page',
            'description': (
                'A/B test comparing the existing 3-step checkout (control) '
                'against the consolidated one-page flow at /checkout/quick/. '
                "Goal: purchase conversion. Promote to `running` from the "
                'admin once you want exposures to start being recorded.'
            ),
            'status': 'draft',
            'variants': [
                {'name': 'control', 'weight': 50},
                {'name': 'one_page', 'weight': 50},
            ],
            'goal': 'purchase',
        },
    )


def reverse(apps, schema_editor):
    Experiment = apps.get_model('experiments', 'Experiment')
    Experiment.objects.filter(key='checkout_flow').delete()


class Migration(migrations.Migration):
    dependencies = [
        ('experiments', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed, reverse),
    ]
