from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True
    dependencies = [
        ('catalog', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Asset3D',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('glb_url', models.URLField(blank=True)),
                ('usdz_url', models.URLField(blank=True)),
                ('poster_url', models.URLField(blank=True)),
                ('glb_size_bytes', models.PositiveIntegerField(default=0)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('product', models.OneToOneField(on_delete=models.deletion.CASCADE, related_name='asset_3d', to='catalog.product')),
            ],
            options={'verbose_name': '3D / AR asset', 'verbose_name_plural': '3D / AR assets'},
        ),
        migrations.CreateModel(
            name='ShoppableVideo',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('video_url', models.URLField()),
                ('markers_json', models.TextField(blank=True, default='[]')),
                ('poster_url', models.URLField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('product', models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='shoppable_videos', to='catalog.product')),
            ],
            options={'ordering': ['-created_at']},
        ),
    ]
