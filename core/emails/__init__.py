"""Transactional-email handlers + templates.

This module subscribes to a curated set of domain events and renders an
email per event. Failures are logged, never raised — a flaky SMTP host
must not block order placement.

Wiring is done by ``core.apps.CoreConfig.ready()`` calling
:func:`register_handlers` once per process. Templates live in
``core/emails/templates/emails/``.
"""

from __future__ import annotations

from core.emails.handlers import register_handlers, send_templated_email

__all__ = ['register_handlers', 'send_templated_email']
