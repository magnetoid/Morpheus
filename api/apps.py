from django.apps import AppConfig


class ApiConfig(AppConfig):
    name = 'api'

    def ready(self) -> None:
        # Pre-build the GraphQL schema so the first request doesn't pay the
        # plugin-discovery latency.
        from api.schema import warm_schema

        warm_schema()
