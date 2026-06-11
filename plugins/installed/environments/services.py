"""Environment services: snapshot, promote, rollback."""

from __future__ import annotations

import logging
from typing import Any

from django.db import transaction
from django.utils import timezone

logger = logging.getLogger('morpheus.environments')


def take_snapshot(environment, *, label: str = '', actor=None) -> EnvironmentSnapshot:  # noqa: F821
    """Capture an environment's overrides into a fresh snapshot."""
    from plugins.installed.environments.models import EnvironmentSnapshot

    payload = {
        'settings_overrides': environment.settings_overrides,
        'theme_overrides': environment.theme_overrides,
        'kind': environment.kind,
        'domain': environment.domain,
    }
    return EnvironmentSnapshot.objects.create(
        environment=environment,
        label=label or f'snapshot-{timezone.now().strftime("%Y%m%d-%H%M%S")}',
        payload=payload,
        created_by=actor,
    )


def diff_snapshots(
    snapshot_a_payload: dict[str, Any], snapshot_b_payload: dict[str, Any]
) -> dict[str, Any]:
    diff: dict[str, Any] = {'changed': {}, 'added': {}, 'removed': {}}
    keys = set(snapshot_a_payload) | set(snapshot_b_payload)
    for k in keys:
        a = snapshot_a_payload.get(k)
        b = snapshot_b_payload.get(k)
        if a == b:
            continue
        if a is None:
            diff['added'][k] = b
        elif b is None:
            diff['removed'][k] = a
        else:
            diff['changed'][k] = {'from': a, 'to': b}
    return diff


def promote(
    *,
    snapshot,
    target,
    actor=None,
    note: str = '',
    confirm: bool = False,
    dry_run: bool = False,
) -> Deployment:  # noqa: F821
    """Apply a snapshot to a target environment, creating a Deployment record."""
    from plugins.installed.environments.models import Deployment

    if target.is_protected and not confirm:
        raise PermissionError(
            f'Cannot deploy to protected environment {target.slug} without confirm=True'
        )

    pre = {
        'settings_overrides': target.settings_overrides,
        'theme_overrides': target.theme_overrides,
        'domain': target.domain,
    }
    diff = diff_snapshots(pre, snapshot.payload)

    deployment = Deployment.objects.create(
        snapshot=snapshot,
        target=target,
        actor=actor,
        note=note,
        diff=diff,
    )
    if dry_run:
        deployment.status = 'pending'
        deployment.save(update_fields=['status'])
        return deployment

    with transaction.atomic():
        target.settings_overrides = snapshot.payload.get('settings_overrides') or {}
        target.theme_overrides = snapshot.payload.get('theme_overrides') or {}
        target.save(update_fields=['settings_overrides', 'theme_overrides', 'updated_at'])
        deployment.status = 'applied'
        deployment.finished_at = timezone.now()
        deployment.save(update_fields=['status', 'finished_at'])
    return deployment


def rollback(deployment) -> None:
    """Rollback a deployment by re-applying its `pre` diff to the target."""
    if deployment.status != 'applied':
        raise ValueError('Only applied deployments can be rolled back')

    target = deployment.target
    diff = deployment.diff or {}
    with transaction.atomic():
        for key, change in (diff.get('changed') or {}).items():
            setattr(target, key, change.get('from'))
        for key in diff.get('added') or {}:
            setattr(target, key, {} if key.endswith('_overrides') else '')
        for key, val in (diff.get('removed') or {}).items():
            setattr(target, key, val)
        target.save()
        deployment.status = 'rolled_back'
        deployment.finished_at = timezone.now()
        deployment.save(update_fields=['status', 'finished_at'])
