from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True
    dependencies = [
        ('auth', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Subscription',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('flavour', models.CharField(choices=[('replenish', 'Replenish'), ('curated', 'Curated')], default='replenish', max_length=10)),
                ('state', models.CharField(choices=[('active', 'Active'), ('paused', 'Paused'), ('cancelled', 'Cancelled')], default='active', max_length=10)),
                ('cadence_days', models.PositiveIntegerField(default=30)),
                ('next_ship_at', models.DateTimeField(db_index=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('cancelled_at', models.DateTimeField(blank=True, null=True)),
                ('customer', models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='+', to='auth.user')),
            ],
            options={'ordering': ['-created_at']},
        ),
        migrations.AddIndex(
            model_name='subscription',
            index=models.Index(fields=['state', 'next_ship_at'], name='subscription__state_a3c4e1_idx'),
        ),
        migrations.CreateModel(
            name='SubscriptionLine',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('quantity', models.PositiveIntegerField(default=1)),
                ('subscription', models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='lines', to='subscriptions_plus.subscription')),
            ],
        ),
        migrations.CreateModel(
            name='SubscriptionShipment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('ship_at', models.DateTimeField(db_index=True)),
                ('state', models.CharField(choices=[('scheduled', 'Scheduled'), ('prepared', 'Prepared'), ('shipped', 'Shipped'), ('skipped', 'Skipped')], default='scheduled', max_length=10)),
                ('subscription', models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='shipments', to='subscriptions_plus.subscription')),
                ('order', models.ForeignKey(blank=True, null=True, on_delete=models.deletion.SET_NULL, related_name='+', to='orders.order')),
            ],
            options={'ordering': ['ship_at']},
        ),
        migrations.CreateModel(
            name='SubscriptionEvent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('kind', models.CharField(choices=[('created', 'Created'), ('paused', 'Paused'), ('resumed', 'Resumed'), ('skipped', 'Skipped'), ('swapped', 'Swapped'), ('cancelled', 'Cancelled')], max_length=10)),
                ('at', models.DateTimeField(auto_now_add=True)),
                ('meta_json', models.TextField(blank=True, default='{}')),
                ('subscription', models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='events', to='subscriptions_plus.subscription')),
            ],
        ),
    ]
