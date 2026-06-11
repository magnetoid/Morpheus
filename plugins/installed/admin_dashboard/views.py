"""Admin dashboard views — re-export shim.

Source files now live under ``views_split/`` split by domain (home,
orders, products, customers, marketing, analytics, ai_insights, apps,
settings, returns, palette). The single-file monolith was 1,640 lines
and growing fast; the split makes future dashboard work survivable.

This shim exists so the existing public import path keeps working::

    from plugins.installed.admin_dashboard import views
    views.orders_list  # → views_split.orders.orders_list

Once every internal caller is migrated to ``from … import views_split``
(or we rename ``views_split`` → ``views`` as a follow-up), this file
will be deleted.
"""

from plugins.installed.admin_dashboard.views_split import *  # noqa: F401, F403
