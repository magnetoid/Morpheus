"""Personalisation plugin — co-purchase / frequently-bought-together rec engine.

Recently-viewed lives in advanced_ecommerce; this plugin adds the
higher-conversion rec type — products customers actually bought
together. Co-purchase rails attribute ~35% of revenue on Amazon-class
shops (anchor + bundle effect).

Phase 1 implements deterministic co-occurrence counts over a rolling
window. Phase 2 (when the self-improvement engine analyzer ships)
can layer LLM reasoning to surface contextual "complete the look"
recommendations beyond raw co-occurrence.
"""

default_app_config = 'plugins.installed.personalisation.apps.PersonalisationConfig'
