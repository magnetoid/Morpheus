from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True
    dependencies = []

    operations = [
        migrations.CreateModel(
            name='Asset',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=200)),
                ('kind', models.CharField(choices=[('image', 'Image'), ('font', 'Font'), ('icon', 'Icon'), ('video', 'Video'), ('other', 'Other')], default='image', max_length=12)),
                ('url', models.URLField()),
                ('tags', models.JSONField(blank=True, default=list)),
                ('width', models.PositiveIntegerField(default=0)),
                ('height', models.PositiveIntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={'ordering': ['-created_at']},
        ),
        migrations.AddIndex(
            model_name='asset',
            index=models.Index(fields=['kind', '-created_at'], name='brand_kit__kind_a3d4f1_idx'),
        ),
        migrations.CreateModel(
            name='DesignTokenSet',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('slug', models.SlugField(max_length=80, unique=True)),
                ('name', models.CharField(max_length=120)),
                ('is_active', models.BooleanField(default=False)),
                ('tokens_json', models.TextField(default='{}')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={'ordering': ['-is_active', 'name']},
        ),
    ]
