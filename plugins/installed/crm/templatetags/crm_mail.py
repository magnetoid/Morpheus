"""Inbox template filters: ``{{ m.subject|mail_header }}`` and ``{{ m|mail_body }}``."""

from __future__ import annotations

from django import template

from plugins.installed.crm.mail_render import header_text, render_body

register = template.Library()

register.filter('mail_header', header_text)
register.filter('mail_body', render_body)
