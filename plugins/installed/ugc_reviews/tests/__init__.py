"""Smoke test for ugc_reviews plugin."""

from __future__ import annotations


def test_plugin_metadata():
    from plugins.installed.ugc_reviews.plugin import UgcReviewsPlugin

    assert UgcReviewsPlugin.name == 'ugc_reviews'
    assert 'reviews' in UgcReviewsPlugin.requires
