"""Admin dashboard views — split into per-domain modules.

Until 2026-05 this was a single 1,640-line ``views.py``. We've kept the
public entry points stable: ``urls.py`` still imports ``views`` and
references ``views.orders_list`` etc., which resolves through the star
imports below. New views should land in the appropriate sub-module
rather than this file.
"""

# ruff: noqa: I001
# Import order in this module matters for star-import resolution
# precedence; the layout below is deliberate.
from __future__ import annotations

# Order matters only for tooling — runtime is fine because each module
# defines disjoint top-level names.
from plugins.installed.admin_dashboard.views_split.home import *  # noqa: F401, F403
from plugins.installed.admin_dashboard.views_split.orders import *  # noqa: F401, F403
from plugins.installed.admin_dashboard.views_split.products import *  # noqa: F401, F403
from plugins.installed.admin_dashboard.views_split.categories import *  # noqa: F401, F403
from plugins.installed.admin_dashboard.views_split.collections import *  # noqa: F401, F403
from plugins.installed.admin_dashboard.views_split.tags import *  # noqa: F401, F403
from plugins.installed.admin_dashboard.views_split.customers import *  # noqa: F401, F403
from plugins.installed.admin_dashboard.views_split.marketing import *  # noqa: F401, F403
from plugins.installed.admin_dashboard.views_split.analytics import *  # noqa: F401, F403
from plugins.installed.admin_dashboard.views_split.ai_insights import *  # noqa: F401, F403
from plugins.installed.admin_dashboard.views_split.apps import *  # noqa: F401, F403
from plugins.installed.admin_dashboard.views_split.settings import *  # noqa: F401, F403
from plugins.installed.admin_dashboard.views_split.system import *  # noqa: F401, F403
from plugins.installed.admin_dashboard.views_split.returns import *  # noqa: F401, F403
from plugins.installed.admin_dashboard.views_split.palette import *  # noqa: F401, F403
from plugins.installed.admin_dashboard.views_split.ai_writers import *  # noqa: F401, F403
from plugins.installed.admin_dashboard.views_split.account import *  # noqa: F401, F403
from plugins.installed.admin_dashboard.views_split import theme_builder as theme_builder_views  # noqa: F401
from plugins.installed.admin_dashboard.views_split import self_improvement as self_improvement_views  # noqa: F401
