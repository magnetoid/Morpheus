"""Markers in guides resolve against the live registry (release_notes/help_markers.py).

ResolveTests pin each kind against real apps. GuideMarkerTests walks every guide
in the tree and fails on a marker that names nothing: the check that keeps a
guide's links true when a page moves or a setting is renamed.
"""

from __future__ import annotations

from django.test import TestCase

from plugins import app_help
from plugins.installed.release_notes.help_markers import Link, resolve
from plugins.registry import app_registry


class ResolveTests(TestCase):
    def test_a_page_of_the_guides_own_app(self):
        self.assertEqual(
            resolve('page', 'reviews', app='reviews'),
            Link('Products › Reviews', '/dashboard/reviews/'),
        )

    def test_a_page_of_another_app(self):
        self.assertEqual(
            resolve('page', 'release_notes/version', app='reviews'),
            Link(
                'Settings › Developer › Version & updates',
                '/dashboard/apps/release_notes/version/',
            ),
        )

    def test_an_apps_settings(self):
        self.assertEqual(
            resolve('settings', 'newsletter', app='reviews'),
            Link('Settings › Marketing › Newsletter', '/dashboard/settings/newsletter/'),
        )

    def test_a_settings_field_shows_its_live_label(self):
        self.assertEqual(
            resolve('field', 'newsletter.winback_enabled', app='newsletter'),
            Link('Send win-back emails', '/dashboard/settings/newsletter/'),
        )

    def test_a_sidebar_section(self):
        self.assertEqual(
            resolve('section', 'orders', app='reviews'), Link('Orders', '/dashboard/orders/')
        )

    def test_another_apps_help(self):
        self.assertEqual(
            resolve('app', 'orders', app='reviews'), Link('Orders', '/dashboard/help/orders/')
        )

    def test_a_marker_that_names_nothing(self):
        for kind, target in (
            ('page', 'no_such_page'),
            ('page', 'no_such_app/x'),
            ('settings', 'reviews'),  # reviews has no settings
            ('field', 'newsletter.no_such_key'),
            ('field', 'newsletter'),
            ('section', 'no_such_section'),
            ('app', 'no_such_app'),
            ('nope', 'reviews'),
        ):
            with self.subTest(kind=kind, target=target):
                self.assertIsNone(resolve(kind, target, app='reviews'))

    def test_a_place_in_an_app_that_is_off_has_no_link(self):
        app_registry.deactivate('reviews')
        self.addCleanup(app_registry.activate, 'reviews')
        self.assertEqual(
            resolve('page', 'reviews', app='reviews'), Link('Products › Reviews', '', off=True)
        )


class GuideMarkerTests(TestCase):
    def test_every_marker_in_every_guide_names_something(self):
        broken = []
        for app in app_help.tree_apps():
            found = app_help.guide(app)
            if found is None:
                continue
            for text, kind, target in app_help.markers(found.body):
                link = resolve(
                    kind, target, app=app, find=app_help.load_manifest, active=lambda _n: True
                )
                if link is None:
                    broken.append(f'{app}: [{text}]({kind}:{target})')
        self.assertEqual(broken, [])
