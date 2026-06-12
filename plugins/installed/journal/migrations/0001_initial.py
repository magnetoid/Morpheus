from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True
    dependencies = [
        ('auth', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Post',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('slug', models.SlugField(unique=True, max_length=200)),
                ('title', models.CharField(max_length=240)),
                ('excerpt', models.TextField(blank=True)),
                ('hero_image', models.URLField(blank=True)),
                ('status', models.CharField(choices=[('draft', 'Draft'), ('scheduled', 'Scheduled'), ('published', 'Published'), ('archived', 'Archived')], default='draft', max_length=12)),
                ('publish_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('search_blob', models.TextField(blank=True, default='')),
                ('author', models.ForeignKey(blank=True, null=True, on_delete=models.deletion.SET_NULL, related_name='+', to='auth.user')),
            ],
            options={'ordering': ['-publish_at', '-created_at']},
        ),
        migrations.AddIndex(
            model_name='post',
            index=models.Index(fields=['status', '-publish_at'], name='journal_pos_status_8d3f2c_idx'),
        ),
        migrations.CreateModel(
            name='Block',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('version', models.PositiveIntegerField(default=1)),
                ('document_json', models.TextField(default='{"version": 1, "blocks": []}')),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('post', models.OneToOneField(on_delete=models.deletion.CASCADE, related_name='body', to='journal.post')),
            ],
        ),
    ]
