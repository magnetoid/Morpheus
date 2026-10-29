"""Celery entry point for the tracking app.

`send_event` POSTs to Google's Measurement Protocol (timeout 6s). Hook
handlers run inside the shopper's request, so the POST is queued here instead
of making every product page, add-to-cart and checkout wait on Google.
"""

from __future__ import annotations

from celery import shared_task


@shared_task(name='tracking.send_event', ignore_result=True, time_limit=30, soft_time_limit=20)
def send_event_task(  # noqa: PLR0913
    *,
    event_name: str,
    params: dict,
    transaction_id: str = '',
    client_id: str = '',
    session_id: str = '',
    user_id: str = '',
    consent: dict | None = None,
) -> None:
    from plugins.installed.tracking.services.measurement_protocol import send_event

    send_event(
        event_name=event_name,
        params=params,
        transaction_id=transaction_id,
        client_id=client_id,
        session_id=session_id,
        user_id=user_id,
        consent=consent,
    )
