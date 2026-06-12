from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True
    dependencies = [
        ('orders', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='CarrierEmission',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('carrier', models.CharField(max_length=24)),
                ('service_level', models.CharField(max_length=24)),
                ('lane_kind', models.CharField(default='domestic', max_length=12)),
                ('g_per_kg_km', models.FloatField(default=0.0)),
                ('last_updated', models.DateTimeField(auto_now=True)),
            ],
            options={'ordering': ['carrier', 'service_level']},
        ),
        migrations.AlterUniqueTogether(
            name='carrieremission',
            unique_together={('carrier', 'service_level', 'lane_kind')},
        ),
        migrations.CreateModel(
            name='OrderShipment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('carrier', models.CharField(blank=True, max_length=24)),
                ('service_level', models.CharField(blank=True, max_length=24)),
                ('rate_id', models.CharField(blank=True, max_length=80)),
                ('cost_cents', models.PositiveIntegerField(default=0)),
                ('g_co2e_estimated', models.FloatField(default=0.0)),
                ('chosen_at', models.DateTimeField(auto_now_add=True)),
                ('order', models.OneToOneField(on_delete=models.deletion.CASCADE, related_name='+', to='orders.order')),
            ],
        ),
    ]
