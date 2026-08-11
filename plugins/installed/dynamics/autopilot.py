"""dynamics — the AI merchandiser autopilot.

A nightly, propose-only merchandiser. It reads the store's OWN signals — which
blocks are live, the bandit's per-segment winners, the propensity distribution,
and running-experiment results — and files ``MerchandisingProposal`` rows into a
human-checkpoint review queue. Nothing is applied automatically; a staff member
Approves (which runs a low-risk config action) or Dismisses each one.

"AI" without the LLM in the hot path: proposals are generated deterministically
from data, then, IF an AI provider is configured, a single bounded offline call
rewrites the titles/rationales in friendlier merchant language (fail-soft to the
templates). ADR 0029: this uses the shared LLM provider for a text task — it
does NOT add an agent class.

`ensure_default_blocks()` is the "zero-config" path: turn Autopilot on and the
store gets sensible self-optimizing blocks with no manual setup.
"""

from __future__ import annotations

import logging

logger = logging.getLogger('morpheus.dynamics')

# The slots Autopilot auto-provisions — the two highest-intent surfaces.
# These MUST be slots the active theme actually renders, or zero-config
# merchandising provisions a block that silently shows nothing. `home_above_grid`
# was the default until v0.36 even though dot_books deliberately dropped that
# slot (its hero leads the page), so every new store got an invisible block.
_DEFAULT_SLOTS = ['home_below_grid', 'pdp_below_form']
_FEATURE_TOP_N = 4


# ── Auto-provisioning (zero-config) ─────────────────────────────────────────


def ensure_default_blocks(*, slots=None) -> int:
    """Idempotently provision an enabled ``autopilot`` block on each slot that has
    none — so a store gets per-visitor self-optimizing merchandising with zero
    manual configuration. Returns the number created."""
    from plugins.installed.dynamics.models import DynamicBlock

    created = 0
    for slot in slots or _DEFAULT_SLOTS:
        if not DynamicBlock.objects.filter(slot=slot, strategy='autopilot').exists():
            DynamicBlock.objects.create(
                name=f'Autopilot — {slot}',
                heading='Recommended for you',
                slot=slot,
                strategy='autopilot',
                enabled=True,
                limit=8,
            )
            created += 1
    return created


# ── Nightly proposal generation ─────────────────────────────────────────────


def generate_proposals() -> dict:
    """Inspect the store's signals and file merchandising proposals (propose-only,
    deduped). Returns ``{'created': n}``."""
    drafts: list[dict] = []
    drafts.extend(_autopilot_draft())
    drafts.extend(_feature_drafts())
    drafts.extend(_experiment_drafts())
    _enrich_with_llm(drafts)
    created = _persist(drafts)
    applied = _auto_apply_actionables() if created and _auto_apply_enabled() else 0
    return {'created': created, 'auto_applied': applied}


def _auto_apply_enabled() -> bool:
    """The merchant's 'skip the review queue for low-risk actions' toggle
    (Settings → Autopilot). Off by default — proposals wait for a human."""
    try:
        from plugins.registry import app_registry

        return bool(app_registry.get('dynamics').get_config().get('auto_apply'))
    except Exception:  # noqa: BLE001
        return False


def _auto_apply_actionables() -> int:
    """Auto-approve the just-filed low-risk (actionable) proposals when the
    merchant has opted in. Insights still wait for a human."""
    from plugins.installed.dynamics.models import MerchandisingProposal

    n = 0
    for p in MerchandisingProposal.objects.filter(
        status='proposed', kind__in=MerchandisingProposal.ACTIONABLE_KINDS
    ):
        if apply_proposal(p, actor=None):
            n += 1
    return n


def _autopilot_draft() -> list[dict]:
    from plugins.installed.dynamics.models import DynamicBlock

    if DynamicBlock.objects.filter(strategy='autopilot', enabled=True).exists():
        return []
    return [
        {
            'kind': 'enable_autopilot',
            'title': 'Turn on Autopilot merchandising',
            'rationale': (
                'No self-optimizing block is live yet. Autopilot ranks products '
                'per visitor and learns from what actually converts — set-and-forget.'
            ),
            'payload': {'slots': _DEFAULT_SLOTS},
            'signature': 'enable_autopilot',
        }
    ]


def _feature_drafts() -> list[dict]:
    """Propose featuring the highest-propensity products that aren't featured yet."""
    from plugins.installed.catalog.models import Product
    from plugins.installed.dynamics.models import DynamicGridItem

    top = list(
        DynamicGridItem.objects.filter(purchase_probability__gt=0)
        .order_by('-purchase_probability')
        .values_list('product_id', 'title', 'purchase_probability')[: _FEATURE_TOP_N * 3]
    )
    unfeatured = set(
        Product.objects.filter(
            pk__in=[pid for pid, _, _ in top], is_featured=False, status='active'
        ).values_list('pk', flat=True)
    )
    picks = [(pid, title) for pid, title, _ in top if pid in unfeatured][:_FEATURE_TOP_N]
    if not picks:
        return []
    names = ', '.join(t for _, t in picks)
    return [
        {
            'kind': 'feature_products',
            'title': f'Feature {len(picks)} high-intent product(s)',
            'rationale': (
                f'These score highest on purchase-propensity but are not featured: {names}. '
                'Featuring surfaces them across the storefront.'
            ),
            'payload': {'product_ids': [str(pid) for pid, _ in picks]},
            'signature': 'feature_products',
        }
    ]


def _experiment_drafts() -> list[dict]:
    """Surface any running experiment whose variant is significantly beating
    control — an informational insight consuming experiments.results_for()."""
    try:
        from plugins.installed.experiments.models import Experiment
        from plugins.installed.experiments.services import results_for
    except Exception:  # noqa: BLE001 — experiments plugin disabled
        return []
    out: list[dict] = []
    for exp in Experiment.objects.filter(status='running')[:20]:
        try:
            res = results_for(exp)
        except Exception:  # noqa: BLE001, S112 — one bad experiment must not stop the rest
            continue
        variants = [v for v in (res.get('variants') or []) if v.get('significant_95')]
        winner = max(variants, key=lambda v: v.get('lift_pct') or 0, default=None)
        if winner and (winner.get('lift_pct') or 0) > 0:
            out.append(
                {
                    'kind': 'winning_strategy',
                    'title': f'"{exp.key}": {winner.get("name")} is winning',
                    'rationale': (
                        f'Variant "{winner.get("name")}" is beating control by '
                        f'{winner.get("lift_pct")}% (95% significant). Consider rolling it out.'
                    ),
                    'payload': {'experiment': exp.key, 'variant': winner.get('name')},
                    'signature': f'winning_strategy:{exp.key}',
                }
            )
    return out


def _enrich_with_llm(drafts: list[dict]) -> None:
    """If an AI provider is configured, rewrite the drafts' titles/rationales in
    warmer merchant language. Bounded, offline, fail-soft — a mock/absent provider
    or any error leaves the deterministic templates untouched."""
    if not drafts:
        return
    try:
        from core.agents.llm import LLMMessage, get_llm_provider

        provider = get_llm_provider()
        if getattr(provider, 'name', '') in ('unconfigured', 'mock', 'base'):
            return
        import json

        lines = [{'i': i, 'title': d['title'], 'why': d['rationale']} for i, d in enumerate(drafts)]
        resp = provider.respond(
            messages=[
                LLMMessage(
                    role='system',
                    content=(
                        'You are a concise e-commerce merchandiser. Rewrite each '
                        'proposal title (<=70 chars) and rationale (<=200 chars) in '
                        'warm, plain merchant language. Return ONLY a JSON list of '
                        '{"i":int,"title":str,"why":str}. Keep the same meaning.'
                    ),
                ),
                LLMMessage(role='user', content=json.dumps(lines)),
            ],
            temperature=0.4,
            max_tokens=600,
        )
        text = getattr(resp, 'text', '') or ''
        start, end = text.find('['), text.rfind(']')
        if start == -1 or end == -1:
            return
        for row in json.loads(text[start : end + 1]):
            i = row.get('i')
            if isinstance(i, int) and 0 <= i < len(drafts):
                drafts[i]['title'] = str(row.get('title') or drafts[i]['title'])[:200]
                drafts[i]['rationale'] = str(row.get('why') or drafts[i]['rationale'])
    except Exception as e:  # noqa: BLE001 — LLM is a nicety, never a dependency
        logger.debug('dynamics: proposal LLM enrich skipped: %s', e)


def _persist(drafts: list[dict]) -> int:
    """Create a row per draft unless an OPEN (proposed) one with the same
    signature already exists."""
    from plugins.installed.dynamics.models import MerchandisingProposal

    open_sigs = set(
        MerchandisingProposal.objects.filter(status='proposed').values_list('signature', flat=True)
    )
    created = 0
    for d in drafts:
        if d['signature'] in open_sigs:
            continue
        MerchandisingProposal.objects.create(
            kind=d['kind'],
            title=d['title'][:200],
            rationale=d['rationale'],
            payload=d.get('payload') or {},
            signature=d['signature'][:200],
        )
        open_sigs.add(d['signature'])
        created += 1
    return created


# ── Human-approved application ──────────────────────────────────────────────


def apply_proposal(proposal, *, actor=None) -> bool:
    """Apply an approved proposal's config action (low-risk only) and audit it.
    Insights just get acknowledged. Returns True if a change was applied."""
    from django.utils import timezone

    from core.audit import services as audit

    if proposal.status != 'proposed':
        return False
    applied = False
    if proposal.kind == 'enable_autopilot':
        ensure_default_blocks(slots=proposal.payload.get('slots'))
        applied = True
    elif proposal.kind == 'feature_products':
        applied = _apply_feature(proposal.payload)
    elif proposal.kind == 'provision_block':
        applied = _apply_provision(proposal.payload)
    # winning_strategy / insight are informational → approving acknowledges them.

    proposal.status = 'approved'
    proposal.reviewed_at = timezone.now()
    proposal.reviewed_by = actor if getattr(actor, 'is_authenticated', False) else None
    proposal.save(update_fields=['status', 'reviewed_at', 'reviewed_by'])
    audit.record(
        event_type='dynamics.proposal_approved',
        actor=actor,
        target=str(proposal.id),
        metadata={'kind': proposal.kind, 'applied': applied},
    )
    return applied


def _apply_feature(payload) -> bool:
    from plugins.installed.catalog.models import Product

    ids = payload.get('product_ids') or []
    if not ids:
        return False
    return Product.objects.filter(pk__in=ids).update(is_featured=True) > 0


def _apply_provision(payload) -> bool:
    slot = payload.get('slot')
    if not slot:
        return False
    return ensure_default_blocks(slots=[slot]) > 0


def dismiss_proposal(proposal, *, actor=None) -> None:
    from django.utils import timezone

    if proposal.status != 'proposed':
        return
    proposal.status = 'dismissed'
    proposal.reviewed_at = timezone.now()
    proposal.reviewed_by = actor if getattr(actor, 'is_authenticated', False) else None
    proposal.save(update_fields=['status', 'reviewed_at', 'reviewed_by'])
