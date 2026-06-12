from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True
    dependencies = [
        ('catalog', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Look',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('slug', models.SlugField(max_length=120, unique=True)),
                ('title', models.CharField(max_length=200)),
                ('description', models.TextField(blank=True)),
                ('cover_image', models.URLField(blank=True)),
                ('is_published', models.BooleanField(default=True)),
                ('is_auto_generated', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={'ordering': ['-created_at']},
        ),
        migrations.CreateModel(
            name='LookItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('order', models.PositiveIntegerField(default=0)),
                ('look', models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='items', to='lookbook.look')),
                ('product', models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='+', to='catalog.product')),
            ],
            options={'ordering': ['order']},
        ),
        migrations.AlterUniqueTogether(
            name='lookitem',
            unique_together={('look', 'product')},
        ),
    ]
