# CodeProposal becomes the store for Janus's technical reports (owner, 2026-10-13).
# Its table had 0 rows on every store: the self-coding loop that wrote it was
# retired in v0.65.0. Fields that still mean something are renamed, so a row that
# did exist keeps its text; the code-only fields go.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('assistant', '0016_delete_learnedskill'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RenameField('codeproposal', 'target_path', 'area'),
        migrations.RenameField('codeproposal', 'rationale', 'problem'),
        migrations.RenameField('codeproposal', 'source', 'fix'),
        migrations.RenameField('codeproposal', 'approver', 'sent_by'),
        migrations.RenameField('codeproposal', 'approved_at', 'sent_at'),
        migrations.RemoveField('codeproposal', 'name'),
        migrations.RemoveField('codeproposal', 'kind'),
        migrations.RemoveField('codeproposal', 'findings'),
        migrations.RemoveField('codeproposal', 'passed'),
        migrations.RemoveField('codeproposal', 'consensus'),
        migrations.RemoveField('codeproposal', 'applied_branch'),
        migrations.RemoveField('codeproposal', 'applied_at'),
        migrations.AddField(
            model_name='codeproposal',
            name='title',
            field=models.CharField(default='', max_length=200),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='codeproposal',
            name='morpheus_version',
            field=models.CharField(blank=True, max_length=32),
        ),
        migrations.AddField(
            model_name='codeproposal',
            name='conversation_key',
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name='codeproposal',
            name='reported_by',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='+',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            model_name='codeproposal',
            name='problem',
            field=models.TextField(),
        ),
        migrations.AlterField(
            model_name='codeproposal',
            name='fix',
            field=models.TextField(blank=True),
        ),
        migrations.AlterField(
            model_name='codeproposal',
            name='status',
            field=models.CharField(
                choices=[('new', 'New'), ('sent', 'Sent'), ('dismissed', 'Dismissed')],
                db_index=True,
                default='new',
                max_length=12,
            ),
        ),
    ]
