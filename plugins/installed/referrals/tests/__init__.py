"""Smoke test for referrals plugin."""

from __future__ import annotations


def test_plugin_metadata():
    from plugins.installed.referrals.app import ReferralsPlugin

    assert ReferralsPlugin.name == 'referrals'
    assert 'loyalty_points' in ReferralsPlugin.requires
