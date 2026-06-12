from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True
    dependencies = [
        ('auth', '0001_initial'),
        ('orders', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='ReferralCode',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('code', models.SlugField(max_length=24, unique=True)),
                ('channel', models.CharField(default='default', max_length=24)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('customer', models.OneToOneField(on_delete=models.deletion.CASCADE, related_name='+', to='auth.user')),
            ],
        ),
        migrations.CreateModel(
            name='Referral',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('code', models.SlugField(max_length=24)),
                ('state', models.CharField(choices=[('pending', 'Pending'), ('credited', 'Credited'), ('reversed', 'Reversed')], default='pending', max_length=12)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('credited_at', models.DateTimeField(blank=True, null=True)),
                ('referrer', models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='referrals_made', to='auth.user')),
                ('referee', models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='referrals_received', to='auth.user')),
                ('order', models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='+', to='orders.order')),
            ],
            options={'ordering': ['-created_at']},
        ),
        migrations.AlterUniqueTogether(
            name='referral',
            unique_together={('referee', 'order')},
        ),
    ]
