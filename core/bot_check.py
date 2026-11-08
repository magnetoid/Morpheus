"""The bot check on public forms: one seam, answered by the app that protects them.

A public form carries `{% bot_check "<form>" %}` (core/templatetags/morph.py) and its view
asks `passes(request, "<form>")` before it acts. The Cloudflare app answers with Turnstile
for the kinds its settings switch on; with no answer the tag renders nothing and every form
passes, so a store without that app keeps working. Kinds: 'contact' (contact, CMS forms, Do
not sell), 'newsletter', 'sign_in' (sign-in, sign-up, password reset, the emailed code) and
'affiliates' (the affiliate application).
"""

from __future__ import annotations

import logging

from django.utils.translation import gettext_lazy as _

from core.hooks import MorpheusEvents, hook_registry

logger = logging.getLogger(__name__)

REFUSED = _('Please confirm you are not a robot, then try again.')


def passes(request, form: str) -> bool:
    """False only when an app protects `form` and the request failed its check."""
    return (
        hook_registry.filter(MorpheusEvents.BOT_CHECK_PASSES, True, request=request, form=form)
        is not False
    )


def widget(context, form: str) -> str:
    """The protecting app's markup for `form` (trusted HTML), or ''."""
    try:
        html = hook_registry.filter(MorpheusEvents.BOT_CHECK_WIDGET, '', form=form, context=context)
    except Exception:  # noqa: BLE001 — never break a page render
        logger.exception('bot check: widget for %s failed', form)
        return ''
    return html if isinstance(html, str) else ''
