from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True
    dependencies = [
        ('auth', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='ChannelPreference',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('channel', models.CharField(choices=[('sms', 'SMS'), ('whatsapp', 'WhatsApp'), ('push', 'PWA push')], max_length=12)),
                ('opted_in_at', models.DateTimeField(auto_now_add=True)),
                ('opted_out_at', models.DateTimeField(blank=True, null=True)),
                ('encrypted_endpoint', models.TextField(blank=True)),
                ('customer', models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='+', to='auth.user')),
            ],
            options={'ordering': ['channel']},
        ),
        migrations.AlterUniqueTogether(
            name='channelpreference',
            unique_together={('customer', 'channel')},
        ),
    ]
