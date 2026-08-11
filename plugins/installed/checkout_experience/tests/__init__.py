"""Smoke test for checkout_experience plugin (no model = no DB needed)."""

from __future__ import annotations


def test_plugin_metadata():
    from plugins.installed.checkout_experience.app import CheckoutExperiencePlugin

    assert CheckoutExperiencePlugin.name == 'checkout_experience'
    assert CheckoutExperiencePlugin.version
    assert 'orders' in CheckoutExperiencePlugin.requires


def test_settings_schema_keys():
    from plugins.installed.checkout_experience.app import CheckoutExperiencePlugin

    schema = CheckoutExperiencePlugin().get_config_schema()
    props = schema['properties']
    assert 'layout' in props
    assert 'express_methods' in props
