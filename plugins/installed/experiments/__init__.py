"""Experiments plugin — in-process A/B testing tied to the existing
tracking hooks. GrowthBook-compatible feature-flag semantics; no
external service required.
"""

default_app_config = 'plugins.installed.experiments.apps.ExperimentsConfig'
