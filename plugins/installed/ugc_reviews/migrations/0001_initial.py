from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True
    dependencies = [
        ('reviews', '0001_initial'),
        ('auth', '0001_initial'),
        ('orders', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='ReviewMedia',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('kind', models.CharField(choices=[('photo', 'Photo'), ('video', 'Video')], max_length=8)),
                ('url', models.URLField()),
                ('width', models.PositiveIntegerField(default=0)),
                ('height', models.PositiveIntegerField(default=0)),
                ('duration_seconds', models.PositiveIntegerField(default=0)),
                ('approved', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('review', models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='media', to='reviews.review')),
            ],
            options={'ordering': ['-created_at']},
        ),
        migrations.CreateModel(
            name='CreatorInvite',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('state', models.CharField(choices=[('invited', 'Invited'), ('accepted', 'Accepted'), ('declined', 'Declined'), ('expired', 'Expired')], default='invited', max_length=12)),
                ('invite_sent_at', models.DateTimeField(auto_now_add=True)),
                ('accepted_at', models.DateTimeField(blank=True, null=True)),
                ('stipend_credit_id', models.CharField(blank=True, max_length=64)),
                ('customer', models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='+', to='auth.user')),
                ('order', models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='+', to='orders.order')),
            ],
            options={'ordering': ['-invite_sent_at']},
        ),
        migrations.AddIndex(
            model_name='creatorinvite',
            index=models.Index(fields=['customer', '-invite_sent_at'], name='ugc_reviews__custome_idx'),
        ),
    ]
