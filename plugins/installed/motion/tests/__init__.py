"""Smoke test for motion plugin."""

from __future__ import annotations


def test_plugin_metadata():
    from plugins.installed.motion.app import MotionPlugin

    assert MotionPlugin.name == 'motion'
    assert MotionPlugin.requires == []


def test_default_intensity():
    from plugins.installed.motion.app import MotionPlugin

    schema = MotionPlugin().get_config_schema()
    assert schema['properties']['intensity']['default'] == 'standard'
