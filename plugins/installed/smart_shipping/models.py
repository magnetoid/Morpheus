"""Per-rate carbon estimate (manual lookup; refreshed from a CSV).

We pre-compute emissions per (carrier, service_level, lane_kind)
so the checkout path stays fast. The lookup table lives in this
model; it can be edited from the dashboard or refreshed by a
Celery beat job.
"""
from __future__ import annotations

from morpheus import models


class CarrierEmission(models.Model):
    carrier = models.CharField(max_length=24, db_index=True)
    service_level = models.CharField(max_length=24, db_index=True)
    lane_kind = models.CharField(max_length=12, default='domestic')
    # g CO2e per kg·km — see
    # https://www.ipcc.ch/report/ar6/wg3/chapter/chapter-7/ for the
    # source ranges we use as defaults.
    g_per_kg_km = models.FloatField(default=0.0)
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('carrier', 'service_level', 'lane_kind')
        ordering = ['carrier', 'service_level']


class OrderShipment(models.Model):
    """Records the rate the shopper chose on the order."""

    order = models.OneToOneField('orders.Order', on_delete=models.CASCADE, related_name='+')
    carrier = models.CharField(max_length=24, blank=True)
    service_level = models.CharField(max_length=24, blank=True)
    rate_id = models.CharField(max_length=80, blank=True)
    cost_cents = models.PositiveIntegerField(default=0)
    g_co2e_estimated = models.FloatField(default=0.0)
    chosen_at = models.DateTimeField(auto_now_add=True)
