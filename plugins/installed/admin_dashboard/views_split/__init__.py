"""Admin dashboard views — split into per-domain modules.

Until 2026-05 this was a single 1,640-line ``views.py``. We've kept the
public entry points stable: ``urls.py`` still imports ``views`` and
references ``views.orders_list`` etc., which resolves through the star
imports below. New views should land in the appropriate sub-module
rather than this file.
"""
from __future__ import annotations

# Order matters only for tooling — runtime is fine because each module
# defines disjoint top-level names.
from plugins.installed.admin_dashboard.views_split.home import *      # noqa: F401, F403
from plugins.installed.admin_dashboard.views_split.orders import *    # noqa: F401, F403
from plugins.installed.admin_dashboard.views_split.products import *  # noqa: F401, F403
from plugins.installed.admin_dashboard.views_split.customers import * # noqa: F401, F403
from plugins.installed.admin_dashboard.views_split.marketing import * # noqa: F401, F403
from plugins.installed.admin_dashboard.views_split.analytics import * # noqa: F401, F403
from plugins.installed.admin_dashboard.views_split.ai_insights import *  # noqa: F401, F403
from plugins.installed.admin_dashboard.views_split.apps import *      # noqa: F401, F403
from plugins.installed.admin_dashboard.views_split.settings import *  # noqa: F401, F403
from plugins.installed.admin_dashboard.views_split.returns import *   # noqa: F401, F403
from plugins.installed.admin_dashboard.views_split.palette import *   # noqa: F401, F403
from plugins.installed.admin_dashboard.views_split.ai_writers import * # noqa: F401, F403
from plugins.installed.admin_dashboard.views_split.account import *    # noqa: F401, F403
