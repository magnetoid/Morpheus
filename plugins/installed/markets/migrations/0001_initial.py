"""Initial migration for the markets plugin."""
from __future__ import annotations

import uuid

import django.db.models.deletion
import djmoney.models.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('catalog', '0008_productimage_webp_image'),
    ]

    operations = [
        migrations.CreateModel(
            name='Market',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('code', models.SlugField(help_text='Stable identifier — used in URLs and per-product price overrides.', max_length=40, unique=True)),
                ('label', models.CharField(max_length=120)),
                ('country_codes', models.JSONField(blank=True, default=list, help_text='List of ISO 3166-1 alpha-2 country codes (e.g. ["US", "CA"]).')),
                ('currency', models.CharField(default='USD', help_text='ISO 4217 currency code prices in this market are quoted in.', max_length=3)),
                ('default_locale', models.CharField(default='en', help_text='Locale code for storefront translations (e.g. "en", "en-GB", "fr").', max_length=10)),
                ('base_price_adjustment_pct', models.DecimalField(decimal_places=2, default=0, help_text='Whole-catalog price multiplier vs the channel base, in %. e.g. 10 = +10% in this market. Per-product overrides in ProductMarketPrice take precedence.', max_digits=6)),
                ('is_active', models.BooleanField(default=True)),
                ('is_default', models.BooleanField(default=False, help_text='Fallback when no country match is found.')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={'ordering': ['label']},
        ),
        migrations.CreateModel(
            name='ProductMarketPrice',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('price_currency', djmoney.models.fields.CurrencyField(default='USD', editable=False, max_length=3)),
                ('price', djmoney.models.fields.MoneyField(decimal_places=2, default_currency='USD', max_digits=14)),
                ('is_visible', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('market', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='product_prices', to='markets.market')),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='market_prices', to='catalog.product')),
            ],
            options={
                'ordering': ['market', 'product'],
                'indexes': [models.Index(fields=['market', 'product'], name='markets_pro_market__c4e8a1_idx')],
                'unique_together': {('market', 'product')},
            },
        ),
    ]
