"""advanced_payments has no models — the gateways are code, and config
(enable toggles, COD instructions) lives in the plugin's PluginConfig via
``contribute_settings_panel``. Kept as an empty stub so the app has a
models module; no migration is needed."""

from django.db import models  # noqa: F401
