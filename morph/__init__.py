"""Django project package.

Importing the Celery app here is required by the standard Django + Celery
pattern so that ``@shared_task`` decorators registered in third-party
apps + plugins resolve to the configured Morpheus Celery app at import
time (via ``celery.current_app``). Without this, ``shared_task.delay()``
falls back to Celery's default unconfigured app — which has an empty
``broker_url`` and defaults to the AMQP transport on localhost:5672,
producing the ``Connection refused`` traceback you'll see on every
Product save in the web container if you skip this line.
"""

from __future__ import annotations

from morph.celery import app as celery_app

__all__ = ('celery_app',)
