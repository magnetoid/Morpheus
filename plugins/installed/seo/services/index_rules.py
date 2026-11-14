"""Writing index rules: one path for the dashboard's form and Linda's tools.

The rule engine (`rules/params.py`) reads `IndexRule` rows through a compiled,
cached ruleset that `seo/signals.py` drops on every instance save and delete. So
every write here goes through `save()` / `delete()` on the instance, never a
queryset `update()`, which would leave the old ruleset serving (the redirects
landmine). The validation the Index rules page applied lives here too, so a rule
Linda writes is refused for the same reasons a merchant's would be.
"""

from __future__ import annotations

from collections.abc import Iterable


class RuleError(ValueError):
    """A rule that cannot be saved; the message is fit for the merchant."""


def _by_id(model, rule_id):
    """The row ``rule_id`` names, or None (an id that is not a UUID names nothing)."""
    from django.core.exceptions import ValidationError

    rid = str(rule_id or '').strip()
    if not rid:
        return None
    try:
        return model.objects.filter(pk=rid).first()
    except (ValidationError, ValueError):
        return None


def _values(raw) -> list[str]:
    """Allowed values from the form's comma list or a tool's list."""
    if raw is None:
        return []
    items: Iterable = raw.split(',') if isinstance(raw, str) else raw
    return [str(v).strip() for v in items if str(v).strip()]


def save_index_rule(
    *,
    param: str,
    policy: str = '',
    allowed_values=None,
    is_active: bool = True,
    note: str = '',
    rule_id: str = '',
):
    """Create a rule, or change the one ``rule_id`` names. Returns the saved row.

    Raises RuleError for a blank parameter, one that would reach the page number
    (`page`, `page*`, `p*`: pagination has its own policy), an unknown policy, or
    a second rule for a parameter that already has one.
    """
    from django.db import IntegrityError, transaction

    from plugins.installed.seo.models import IndexRule
    from plugins.installed.seo.rules.params import captures_reserved

    param = (param or '').strip().lower()
    policy = (policy or IndexRule.POLICY_CONSOLIDATE).strip()
    if not param:
        raise RuleError('Give the rule a parameter name.')
    if captures_reserved(param):
        # Rejects `page*` and `p*` as well as `page`. The wildcard forms matter
        # more, not less: a `page*` rule set to "block" would put
        # `Disallow: /*?*page` in robots.txt and stop crawlers reaching page 2 of
        # every listing in the shop.
        raise RuleError(
            f'“{param}” would apply to the page number, which has its own policy: '
            'page 2 stays indexable and canonical to itself, and a number past the '
            'end is a 404. A rule here could only break that.'
        )
    if policy not in {c[0] for c in IndexRule.POLICY_CHOICES}:
        raise RuleError(
            f'Unknown policy “{policy}”. Use one of: '
            + ', '.join(c[0] for c in IndexRule.POLICY_CHOICES)
            + '.'
        )
    row = _by_id(IndexRule, rule_id) or IndexRule()
    row.param = param
    row.policy = policy
    row.allowed_values = _values(allowed_values)
    row.is_active = bool(is_active)
    row.note = (note or '').strip()[:200]
    try:
        with transaction.atomic():
            row.save()
    except IntegrityError as e:
        raise RuleError(f'There is already a rule for “{param}”.') from e
    return row


def delete_index_rule(*, rule_id: str = '', param: str = '') -> bool:
    """Delete one rule by id or by parameter. True when a row went.

    An instance delete, not a queryset delete: post_delete is what drops the
    compiled ruleset, and a rule that keeps being applied after it was removed is
    worse than one that never worked.
    """
    from plugins.installed.seo.models import IndexRule

    row = _by_id(IndexRule, rule_id)
    if row is None and (param or '').strip():
        row = IndexRule.objects.filter(param=param.strip().lower()).first()
    if row is None:
        return False
    row.delete()
    return True


def seed_recommended() -> int:
    """Add the recommended starter rules that are missing; change nothing else."""
    from plugins.installed.seo.models import IndexRule
    from plugins.installed.seo.rules.params import RECOMMENDED_RULES

    created = 0
    for param, policy, note in RECOMMENDED_RULES:
        _, was_created = IndexRule.objects.get_or_create(
            param=param, defaults={'policy': policy, 'note': note}
        )
        created += int(was_created)
    return created


def rule_row(row) -> dict:
    """One rule as plain data (Linda's tools)."""
    return {
        'id': str(row.pk),
        'param': row.param,
        'policy': row.policy,
        'allowed_values': list(row.allowed_values or []),
        'is_active': bool(row.is_active),
        'note': row.note or '',
    }
