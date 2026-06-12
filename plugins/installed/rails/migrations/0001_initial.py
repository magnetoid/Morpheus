from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True
    dependencies = [
        ('catalog', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='CuratedRail',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('slug', models.CharField(max_length=64, unique=True, db_index=True)),
                ('title', models.CharField(blank=True, max_length=120)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('products', models.ManyToManyField(blank=True, related_name='curated_in_rails', to='catalog.product')),
            ],
            options={'ordering': ['slug']},
        ),
    ]
