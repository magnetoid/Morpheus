from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('morph_i18n', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='translation',
            name='reviewed',
            field=models.BooleanField(db_default=True, default=True),
        ),
    ]
