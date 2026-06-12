from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True
    dependencies = [
        ('auth', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='OneClickToken',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('encrypted_payload', models.TextField()),
                ('device_label', models.CharField(blank=True, max_length=120)),
                ('last_used_at', models.DateTimeField(blank=True, null=True)),
                ('expires_at', models.DateTimeField()),
                ('revoked_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('customer', models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='one_click_tokens', to='auth.user')),
            ],
            options={'ordering': ['-created_at']},
        ),
        migrations.AddIndex(
            model_name='oneclicktoken',
            index=models.Index(fields=['customer', '-created_at'], name='one_click__custome_idx'),
        ),
    ]
