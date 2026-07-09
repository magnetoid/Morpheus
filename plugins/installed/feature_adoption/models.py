"""Feature-adoption aggregates.

Deliberately coarse: one row per (day, plugin, surface) — no per-event rows,
no PII, no visitor identity. Just "how much did each plugin's surfaces get
used, per day." Written only by the hourly flush task (see ``tracking.py``).
"""

from __future__ import annotations

from django.db import models


class FeatureUsageDay(models.Model):
    """Daily per-plugin usage count for one surface."""

    day = models.DateField(db_index=True)
    plugin = models.CharField(max_length=80)
    surface = models.CharField(max_length=20)  # 'dashboard' | 'agent_tool'
    count = models.PositiveIntegerField(default=0)

    class Meta:
        app_label = 'feature_adoption'
        ordering = ['-day', 'plugin']
        unique_together = ('day', 'plugin', 'surface')
        indexes = [models.Index(fields=['plugin', '-day'])]

    def __str__(self) -> str:
        return f'{self.day} {self.plugin}/{self.surface}={self.count}'
