"""Per-merchant observability GraphQL queries."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import strawberry

from api.graphql_permissions import has_scope, require_authenticated


@strawberry.type
class MetricPoint:
    bucket: str
    value: float
    sample_count: int


@strawberry.type
class MetricSeries:
    metric: str
    granularity: str
    points: list[MetricPoint]


@strawberry.type
class ObservabilityQueryExtension:
    @strawberry.field(description='Per-channel metric series. Requires read:metrics scope.')
    def metric_series(
        self,
        info: strawberry.Info,
        metric: str,
        granularity: str = 'hour',
        hours: int = 24,
        channel_id: strawberry.ID | None = None,
    ) -> MetricSeries:
        from plugins.installed.observability.models import MerchantMetric

        require_authenticated(info)
        if not has_scope(info, 'read:metrics'):
            return MetricSeries(metric=metric, granularity=granularity, points=[])

        cutoff = datetime.now(UTC) - timedelta(hours=max(1, min(hours, 24 * 30)))
        qs = MerchantMetric.objects.filter(
            metric=metric,
            granularity=granularity,
            bucket__gte=cutoff,
        )
        if channel_id is not None:
            qs = qs.filter(channel_id=str(channel_id))
        else:
            qs = qs.filter(channel__isnull=True) | qs

        return MetricSeries(
            metric=metric,
            granularity=granularity,
            points=[
                MetricPoint(
                    bucket=row.bucket.isoformat(),
                    value=row.value,
                    sample_count=row.sample_count,
                )
                for row in qs.order_by('bucket')[:5000]
            ],
        )

    @strawberry.field(description='List metric names this server tracks.')
    def supported_metrics(self, info: strawberry.Info) -> list[str]:
        from plugins.installed.observability.services import supported_metrics

        return list(supported_metrics())
