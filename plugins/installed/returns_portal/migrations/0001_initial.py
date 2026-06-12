from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True
    dependencies = [
        ('auth', '0001_initial'),
        ('orders', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='ReturnRequest',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('state', models.CharField(choices=[('requested', 'Requested'), ('approved', 'Approved'), ('received', 'Received'), ('refunded', 'Refunded'), ('exchanged', 'Exchanged'), ('store_credit', 'Store credit issued'), ('rejected', 'Rejected')], default='requested', max_length=16)),
                ('resolution', models.CharField(choices=[('refund', 'Refund'), ('exchange', 'Exchange'), ('store_credit', 'Store credit')], default='exchange', max_length=12)),
                ('reason', models.CharField(blank=True, max_length=200)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('order', models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='+', to='orders.order')),
                ('customer', models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='+', to='auth.user')),
            ],
            options={'ordering': ['-created_at']},
        ),
        migrations.CreateModel(
            name='ReturnItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('quantity', models.PositiveIntegerField(default=1)),
                ('request', models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='items', to='returns_portal.returnrequest')),
                ('line', models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='+', to='orders.orderline')),
            ],
        ),
        migrations.CreateModel(
            name='ReturnFeedback',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('what_went_wrong', models.TextField(blank=True)),
                ('what_would_have_made_it_right', models.TextField(blank=True)),
                ('nps_score', models.IntegerField(default=0)),
                ('routed_to_crm_at', models.DateTimeField(blank=True, null=True)),
                ('submitted_at', models.DateTimeField(auto_now_add=True)),
                ('request', models.OneToOneField(on_delete=models.deletion.CASCADE, related_name='feedback', to='returns_portal.returnrequest')),
            ],
        ),
    ]
