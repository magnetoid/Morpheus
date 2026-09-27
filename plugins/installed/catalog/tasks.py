"""Celery entry point for the catalog app.

Autodiscovery imports only ``<installed app>.tasks``, so the Typesense sync
tasks in ``search/tasks.py`` were never registered in the worker: every
``upsert_product_task.delay()`` from a product save was rejected as
NotRegistered. Importing them here registers them at worker boot.
"""

from plugins.installed.catalog.search.tasks import (  # noqa: F401
    delete_product_task,
    reindex_all_task,
    upsert_product_task,
)
