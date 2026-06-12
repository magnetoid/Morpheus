from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True
    dependencies = [
        ('auth', '0001_initial'),
        ('catalog', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Drop',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('starts_at', models.DateTimeField(db_index=True)),
                ('ends_at', models.DateTimeField(blank=True, null=True)),
                ('state', models.CharField(choices=[('scheduled', 'Scheduled'), ('live', 'Live'), ('closed', 'Closed')], default='scheduled', max_length=12)),
                ('initial_stock', models.PositiveIntegerField(default=0)),
                ('notes', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('product', models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='+', to='catalog.product')),
            ],
            options={'ordering': ['starts_at']},
        ),
        migrations.AddIndex(
            model_name='drop',
            index=models.Index(fields=['state', 'starts_at'], name='drops_drop__state_a1c2b3_idx'),
        ),
        migrations.CreateModel(
            name='DropTicket',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('position', models.PositiveIntegerField(default=0)),
                ('raffle_seed', models.CharField(blank=True, max_length=64)),
                ('invited_at', models.DateTimeField(auto_now_add=True)),
                ('won_at', models.DateTimeField(blank=True, null=True)),
                ('drop', models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='tickets', to='drops.drop')),
                ('customer', models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='+', to='auth.user')),
            ],
            options={'ordering': ['position']},
        ),
        migrations.AlterUniqueTogether(
            name='dropticket',
            unique_together={('drop', 'customer')},
        ),
        migrations.CreateModel(
            name='Waitlist',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('joined_at', models.DateTimeField(auto_now_add=True)),
                ('notified_at', models.DateTimeField(blank=True, null=True)),
                ('customer', models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='+', to='auth.user')),
                ('product', models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='+', to='catalog.product')),
            ],
            options={'ordering': ['joined_at']},
        ),
        migrations.AlterUniqueTogether(
            name='waitlist',
            unique_together={('customer', 'product')},
        ),
    ]
