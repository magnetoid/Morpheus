from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True
    dependencies = [
        ('auth', '0001_initial'),
        ('catalog', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='SavedItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('moved_at', models.DateTimeField(auto_now_add=True)),
                ('snapshotted_price_cents', models.PositiveIntegerField(default=0)),
                ('snapshotted_in_stock', models.BooleanField(default=True)),
                ('customer', models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='+', to='auth.user')),
                ('product', models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='+', to='catalog.product')),
            ],
            options={'ordering': ['-moved_at']},
        ),
        migrations.AlterUniqueTogether(
            name='saveditem',
            unique_together={('customer', 'product')},
        ),
        migrations.CreateModel(
            name='PriceSnapshot',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('price_cents', models.PositiveIntegerField(default=0)),
                ('in_stock', models.BooleanField(default=True)),
                ('observed_at', models.DateTimeField(auto_now_add=True)),
                ('product', models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='+', to='catalog.product')),
            ],
            options={'ordering': ['-observed_at']},
        ),
        migrations.AddIndex(
            model_name='pricesnapshot',
            index=models.Index(fields=['product', '-observed_at'], name='save_for_l_product_d2a2c1_idx'),
        ),
        migrations.CreateModel(
            name='SharedWishlist',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('token', models.SlugField(max_length=64, unique=True)),
                ('title', models.CharField(blank=True, max_length=120)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('expires_at', models.DateTimeField(blank=True, null=True)),
                ('customer', models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='+', to='auth.user')),
            ],
        ),
    ]
