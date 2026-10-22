from django.db import migrations, models


class Migration(migrations.Migration):
    """The tables of PromptTemplate, AIExperiment, DemandForecast and AgentMemory, and
    AIInteraction.prompt_template, which v0.122.0 left behind (docs/plans/apps-consolidation-2026-10.md)."""

    dependencies = [('ai_assistant', '0007_forget_unused_models')]

    morpheus_contract = 'v0.122.0, the previous release, took these four models and AIInteraction.prompt_template out of the code.'

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.CreateModel(
                    name='PromptTemplate',
                    fields=[('id', models.BigAutoField(primary_key=True))],
                    options={'db_table': 'ai_assistant_prompttemplate'},
                ),
                migrations.CreateModel(
                    name='AIExperiment',
                    fields=[('id', models.BigAutoField(primary_key=True))],
                    options={'db_table': 'ai_assistant_aiexperiment'},
                ),
                migrations.CreateModel(
                    name='DemandForecast',
                    fields=[('id', models.BigAutoField(primary_key=True))],
                    options={'db_table': 'ai_assistant_demandforecast'},
                ),
                migrations.CreateModel(
                    name='AgentMemory',
                    fields=[('id', models.BigAutoField(primary_key=True))],
                    options={'db_table': 'ai_assistant_agentmemory'},
                ),
                migrations.AddField(
                    model_name='aiinteraction',
                    name='prompt_template',
                    field=models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=models.SET_NULL,
                        to='ai_assistant.prompttemplate',
                    ),
                ),
            ],
        ),
        migrations.RemoveField(model_name='aiinteraction', name='prompt_template'),
        migrations.DeleteModel(name='AIExperiment'),
        migrations.DeleteModel(name='PromptTemplate'),
        migrations.DeleteModel(name='DemandForecast'),
        migrations.DeleteModel(name='AgentMemory'),
    ]
