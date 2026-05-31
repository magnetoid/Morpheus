"""Nightly tier + RFM recompute."""

from __future__ import annotations

from celery import shared_task

from plugins.installed.loyalty_points.services_rfm import compute_all as compute_rfm
from plugins.installed.loyalty_points.services_tiers import assign_all as assign_tiers


@shared_task(name='loyalty.assign_tiers')
def assign_tiers_task() -> dict:
    return assign_tiers()


@shared_task(name='loyalty.compute_rfm')
def compute_rfm_task() -> dict:
    return compute_rfm()
