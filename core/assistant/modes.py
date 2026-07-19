"""Linda conversation modes — a tool-palette scope system.

Each mode whitelists a set of tool scopes. The Assistant runtime
filters the available tools by the active mode before passing them
to the LLM, so a "support" conversation can refund an order but not
delete a product.

Modes are merchant-facing; the merchant picks one per conversation
from a chip selector on the Linda page. Mode names are stable —
analytics + audit log queries reference them.

Design:
  * `general` — every tool is fair game (current behaviour, default).
  * `sales`   — read-only catalog + orders + customers + cart help.
  * `support` — order ops (fulfill, cancel, refund) + customer lookup.
  * `ops`     — catalog + inventory writes + content drafting.
  * `dev`     — full access + diagnostics (logs, fs, plugin lifecycle).

Wildcard `*` in a mode's scope list means "every tool", regardless
of what scopes the tool declares.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class AssistantMode:
    """One row in the mode catalogue."""

    slug: str
    label: str  # short, capitalised — shown in the picker chip
    description: str  # one-line summary for the tooltip
    scopes: tuple[str, ...]
    # Lucide icon name; the picker chip displays this in front of the
    # label so each mode has a visual signature.
    icon: str = 'sparkles'


_WILDCARD = ('*',)


MODES: tuple[AssistantMode, ...] = (
    AssistantMode(
        slug='general',
        label='General',
        description='Full access — every tool Linda has. Use when you want her to figure out the right action herself.',
        scopes=_WILDCARD,
        icon='sparkles',
    ),
    AssistantMode(
        slug='sales',
        label='Sales',
        description='Read-only browsing + cart help. Linda can search catalogs, look up products, and add to a customer cart — never edits a product or order.',
        scopes=(
            'catalog.read',
            'analytics.read',
            'cart.read',
            'cart.write',
            'orders.read',
            'customers.read',
        ),
        icon='shopping-bag',
    ),
    AssistantMode(
        slug='support',
        label='Support',
        description='Order lifecycle for customer service — fulfill, ship, cancel, refund. Cannot touch the catalog or inventory.',
        scopes=(
            'orders.read',
            'orders.write',
            'orders.cancel',
            'customers.read',
            'catalog.read',
        ),
        icon='headphones',
    ),
    AssistantMode(
        slug='ops',
        label='Operations',
        description='Day-to-day store operations — edit products, manage inventory, draft copy. No destructive deletes.',
        scopes=(
            'catalog.read',
            'catalog.write',
            'inventory.read',
            'inventory.write',
            'orders.read',
            'orders.write',
            'analytics.read',
            'content.write',
        ),
        icon='settings',
    ),
    AssistantMode(
        slug='dev',
        label='Developer',
        description='Full access PLUS diagnostics (logs, filesystem, plugin lifecycle). Reserved for engineers; sensitive output.',
        scopes=_WILDCARD + ('diagnostics.read',),
        icon='terminal',
    ),
)


_BY_SLUG = {m.slug: m for m in MODES}
DEFAULT_MODE = 'general'


def get_mode(slug: str | None) -> AssistantMode:
    """Resolve a mode by slug. Falls back to ``general`` for unknown /
    None inputs so the Assistant never crashes on a typo.

    NOTE: this performs NO entitlement check — a client can name any mode. Use
    ``resolve_mode(slug, user)`` at request boundaries so the acting user can't
    select a mode above their ceiling (core audit S5/H1).
    """
    return _BY_SLUG.get((slug or '').strip().lower(), _BY_SLUG[DEFAULT_MODE])


def allowed_modes_for(user) -> set[str]:
    """Modes the acting user may use. ``dev`` exposes diagnostics (filesystem,
    logs, plugin lifecycle) and is engineer-only (superuser); everything else is
    available to staff. The Assistant view is already staff-gated, so a non-staff
    caller reaching here gets no elevated modes."""
    if user is None:
        return set()
    if getattr(user, 'is_superuser', False):
        return {m.slug for m in MODES}
    if getattr(user, 'is_staff', False):
        return {m.slug for m in MODES if m.slug != 'dev'}
    return set()


def resolve_mode(slug: str | None, user) -> AssistantMode:
    """Server-side mode resolution: honour the client's requested mode only when
    the acting user is entitled to it; otherwise fall back to the user's default
    (``general`` for staff). A client can never select a mode above its ceiling,
    and an unknown/garbage slug can't escalate to a wildcard — the S5/H1 fix.
    """
    allowed = allowed_modes_for(user)
    want = (slug or '').strip().lower()
    if want in allowed and want in _BY_SLUG:
        return _BY_SLUG[want]
    if DEFAULT_MODE in allowed:
        return _BY_SLUG[DEFAULT_MODE]
    # No entitlements (defensive — non-staff shouldn't reach the assistant):
    # the narrowest read-mostly mode, never the wildcard.
    return _BY_SLUG['sales']


def filter_tools_by_mode(tools: list, mode_slug: str | None) -> list:
    """Return the subset of ``tools`` allowed by the named mode.

    A tool is allowed when EITHER:
      * the mode lists `*` in its scopes (wildcard);
      * the tool has no declared scopes (treated as public);
      * the tool's scope list intersects the mode's scope list.

    Unknown mode slugs default to ``general`` (wildcard) so the
    Assistant never silently strips Linda's capabilities.
    """
    mode = get_mode(mode_slug)
    if '*' in mode.scopes:
        return list(tools)
    allowed = set(mode.scopes)
    out: list = []
    for t in tools:
        scopes = list(getattr(t, 'scopes', None) or [])
        if not scopes:
            out.append(t)  # public tools always reachable
            continue
        if allowed.intersection(scopes):
            out.append(t)
    return out
