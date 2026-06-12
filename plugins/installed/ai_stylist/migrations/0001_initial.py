from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True
    dependencies = [
        ('auth', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='StylistSession',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('session_hash', models.CharField(max_length=64, unique=True, db_index=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('last_seen_at', models.DateTimeField(auto_now=True)),
                ('customer', models.ForeignKey(blank=True, null=True, on_delete=models.deletion.SET_NULL, related_name='+', to='auth.user')),
            ],
        ),
        migrations.CreateModel(
            name='StylistTurn',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('role', models.CharField(max_length=12)),
                ('content', models.TextField(blank=True)),
                ('at', models.DateTimeField(auto_now_add=True)),
                ('session', models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='turns', to='ai_stylist.stylistsession')),
            ],
        ),
        migrations.AddIndex(
            model_name='stylistturn',
            index=models.Index(fields=['session', '-at'], name='ai_stylist__session_3d6b27_idx'),
        ),
    ]
