"""Per-class confidence + reversibility matrix.

The dashboard renders this; the analyzer reads it to decide whether
a recommendation transitions to `propose` (show in UI), `auto_apply`
(execute without human approval), or stays as `advise`.

The defaults below mirror the plan's recommended thresholds. Merchants
override per-class via settings.SELF_IMPROVEMENT['policy'][<class>]
or per-instance via the dashboard's Settings tab.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.conf import settings


@dataclass(slots=True)
class ClassPolicy:
    name: str
    enabled: bool
    auto_apply_threshold: float
    propose_threshold: float
    reversible: bool
    description: str


# Order mirrors the architectural plan §6.
DEFAULT_POLICY: dict[str, dict] = {
    # Data-only auto-fixes
    'seo_gap': {
        'enabled': True,
        'auto': 0.85,
        'propose': 0.60,
        'reversible': True,
        'description': 'Missing alt/meta/OG fields on products + pages.',
    },
    'dead_link': {
        'enabled': True,
        'auto': 0.90,
        'propose': 0.70,
        'reversible': True,
        'description': 'Internal redirects that 404.',
    },
    'zero_search': {
        'enabled': True,
        'auto': 0.80,
        'propose': 0.60,
        'reversible': True,
        'description': 'Searches returning no results — propose synonyms.',
    },
    # Code-touching auto-PRs
    'dep_bump_patch': {
        'enabled': True,
        'auto': 0.85,
        'propose': 0.60,
        'reversible': True,
        'description': 'Patch-level dependency bumps with green tests.',
    },
    'cve_patch': {
        'enabled': True,
        'auto': 0.90,
        'propose': 0.70,
        'reversible': True,
        'description': 'CVE patches gated by reachability analysis.',
    },
    'csp_drift': {
        'enabled': True,
        'auto': 0.75,
        'propose': 0.50,
        'reversible': True,
        'description': 'CSP allowlist updates after a 24h legitimate-traffic check.',
    },
    'slow_query': {
        'enabled': True,
        'auto': 0.0,
        'propose': 0.50,
        'reversible': False,
        'description': 'Add index suggestions — ADVISE ONLY; migrations are protected.',
    },
    'lighthouse_regression': {
        'enabled': True,
        'auto': 0.90,
        'propose': 0.70,
        'reversible': True,
        'description': 'Image regressions resolved via AVIF re-encode.',
    },
    'flaky_test': {
        'enabled': True,
        'auto': 0.95,
        'propose': 0.70,
        'reversible': True,
        'description': 'Quarantine flaky tests after N retries.',
    },
    # Code-quality
    'style_fix': {
        'enabled': True,
        'auto': 0.95,
        'propose': 0.90,
        'reversible': True,
        'description': 'ruff --fix output — deterministic style/format.',
    },
    'missing_types': {
        'enabled': True,
        'auto': 0.90,
        'propose': 0.70,
        'reversible': True,
        'description': 'Missing type hints on public APIs (mypy-verified).',
    },
    'dead_code': {
        'enabled': True,
        'auto': 0.0,
        'propose': 0.60,
        'reversible': False,
        'description': 'Unused defs — ADVISE ONLY; may be re-exported.',
    },
    'complexity_spike': {
        'enabled': True,
        'auto': 0.0,
        'propose': 0.60,
        'reversible': False,
        'description': 'Cyclomatic complexity jumped > +5 — ADVISE ONLY.',
    },
    'bandit_finding': {
        'enabled': True,
        'auto': 0.0,
        'propose': 0.70,
        'reversible': True,
        'description': 'Bandit medium+ findings — PR only, never auto-merge.',
    },
    # Vibecoding-specific
    'upstream_sync': {
        'enabled': True,
        'auto': 0.90,
        'propose': 0.70,
        'reversible': True,
        'description': 'Cherry-pick upstream commits on non-customized files.',
    },
    'error_cluster': {
        'enabled': True,
        'auto': 0.0,
        'propose': 0.60,
        'reversible': False,
        'description': 'Server-side error clusters — ADVISE ONLY.',
    },
}


def policy_for(class_name: str) -> ClassPolicy:
    """Return the effective policy for a class. Settings overrides defaults."""
    base = DEFAULT_POLICY.get(
        class_name,
        {
            'enabled': True,
            'auto': 0.0,
            'propose': 0.50,
            'reversible': False,
            'description': f'Unknown class {class_name!r} — advise only.',
        },
    )
    overrides = (
        (getattr(settings, 'SELF_IMPROVEMENT', None) or {}).get('policy', {}).get(class_name, {})
    )
    merged = {**base, **overrides}
    return ClassPolicy(
        name=class_name,
        enabled=bool(merged.get('enabled', True)),
        auto_apply_threshold=float(merged.get('auto', 0.0)),
        propose_threshold=float(merged.get('propose', 0.5)),
        reversible=bool(merged.get('reversible', False)),
        description=str(merged.get('description', '')),
    )


def all_policies() -> list[ClassPolicy]:
    """Return policies for every known class, in display order."""
    return [policy_for(name) for name in DEFAULT_POLICY]


def decide_action(*, class_name: str, confidence: float, is_customization_safe: bool = True) -> str:
    """Return one of `auto_apply`, `propose`, `advise`, `suppress`.

    `suppress` indicates the class is disabled in policy or the
    customization safety gate blocks an otherwise-eligible recommendation.
    """
    pol = policy_for(class_name)
    if not pol.enabled:
        return 'suppress'
    if (
        pol.auto_apply_threshold > 0
        and confidence >= pol.auto_apply_threshold
        and is_customization_safe
    ):
        return 'auto_apply'
    if confidence >= pol.propose_threshold:
        return 'propose'
    return 'advise'


def export_for_dashboard() -> list[dict[str, Any]]:
    """Serialise every policy for the Settings tab table render."""
    return [
        {
            'name': p.name,
            'enabled': p.enabled,
            'auto_apply_threshold': p.auto_apply_threshold,
            'propose_threshold': p.propose_threshold,
            'reversible': p.reversible,
            'description': p.description,
        }
        for p in all_policies()
    ]
