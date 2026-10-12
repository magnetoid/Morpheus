"""`{% load membership_tags %}` for the subscriptions app's storefront blocks."""

from __future__ import annotations

from django import template

register = template.Library()


@register.simple_tag
def membership_plans_exist() -> bool:
    """Whether there is an active plan to join, so links to /membership/ lead somewhere."""
    from plugins.installed.subscriptions.models import Plan

    return Plan.objects.filter(is_active=True).exists()
