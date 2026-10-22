from django.db import migrations


class Migration(migrations.Migration):
    """PromptTemplate, AIExperiment, DemandForecast, AgentMemory and
    AIInteraction.prompt_template leave Django's state; nothing read or wrote them.
    Their tables stay until v0.122.1, so v0.121.0 still runs if a store is put back
    (docs/plans/apps-consolidation-2026-10.md, Wave 1)."""

    dependencies = [('ai_assistant', '0006_knowledgechunk')]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveField(model_name='aiinteraction', name='prompt_template'),
                migrations.DeleteModel(name='AIExperiment'),
                migrations.DeleteModel(name='PromptTemplate'),
                migrations.DeleteModel(name='DemandForecast'),
                migrations.DeleteModel(name='AgentMemory'),
            ],
        ),
    ]
