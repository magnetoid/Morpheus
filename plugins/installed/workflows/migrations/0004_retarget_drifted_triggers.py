"""Repoint existing workflows at the event names that actually fire.

`TRIGGER_CHOICES` carried two names no event bus ever emits: `customer.created`
(the real event is `customer.registered`) and `agent.run_failed` (really
`agent.run.failed`). The engine registers one listener per choice
(`engine.register_hook_listeners`), so a merchant who built a workflow on either
trigger got a listener bound to an event that never fires — the workflow simply
never ran, with nothing to indicate why.

Rewrites saved rows onto the correct names so existing workflows start working
rather than silently staying dead. Reversible.
"""

from django.db import migrations

_RENAMES = {
    'customer.created': 'customer.registered',
    'agent.run_failed': 'agent.run.failed',
}


def forwards(apps, schema_editor):
    Workflow = apps.get_model('workflows', 'Workflow')
    for old, new in _RENAMES.items():
        Workflow.objects.filter(trigger=old).update(trigger=new)


def backwards(apps, schema_editor):
    Workflow = apps.get_model('workflows', 'Workflow')
    for old, new in _RENAMES.items():
        Workflow.objects.filter(trigger=new).update(trigger=old)


class Migration(migrations.Migration):
    dependencies = [('workflows', '0003_alter_workflow_trigger')]
    operations = [migrations.RunPython(forwards, backwards)]
