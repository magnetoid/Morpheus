"""Morpheus self-improvement engine — autonomic loop + code review + drift tracking.

See docs/plans/self-improvement-engine.md for the architecture (v2).
Position: core, not plugin. Cannot be disabled. Only per-class
confidence thresholds in `SELF_IMPROVEMENT` settings are configurable.
"""

default_app_config = 'core.self_improvement.apps.SelfImprovementConfig'
