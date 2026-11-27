"""A server error's group is where it was raised, not the handler every request runs through.

The fingerprint was the exception class plus the three OUTERMOST frames: Django's
handler, its middleware and dispatch, the same for every view. A KeyError in one
view and another in a second view were one group, and every dashboard app page
goes through one router view, so one class of error on any app page was one group.
"""

from __future__ import annotations

import json

from django.test import SimpleTestCase

from core.errors.services import _fingerprint_server


def _middle(view):
    return view()


def _dispatch(view):
    # Stands in for Django's handler, middleware and router: the same outer frames.
    return _middle(view)


def _caught(view) -> BaseException:
    try:
        _dispatch(view)
    except Exception as exc:  # noqa: BLE001
        return exc
    raise AssertionError('the view did not raise')


def view_a():
    return {}['missing']


def view_b():
    return {}['missing']


def parse_a():
    return json.loads('{')


def parse_b():
    return json.loads('{')


def _compiled_view(blank_lines: int):
    """A view whose raise moves down the file, as an edit above it would move it."""
    source = '\n' * blank_lines + 'def view_c():\n    return {}["missing"]\n'
    namespace: dict = {}
    exec(compile(source, 'plugins/installed/shop/views.py', 'exec'), namespace)  # noqa: S102
    return namespace['view_c']


class ServerFingerprintTests(SimpleTestCase):
    def test_two_views_behind_one_dispatcher_are_two_groups(self):
        self.assertNotEqual(
            _fingerprint_server(_caught(view_a)), _fingerprint_server(_caught(view_b))
        )

    def test_the_same_raise_site_twice_is_one_group(self):
        self.assertEqual(_fingerprint_server(_caught(view_a)), _fingerprint_server(_caught(view_a)))

    def test_standard_library_frames_do_not_hide_the_caller(self):
        # json raises from its own frames; the group is the code that called it.
        self.assertNotEqual(
            _fingerprint_server(_caught(parse_a)), _fingerprint_server(_caught(parse_b))
        )

    def test_an_edit_elsewhere_in_the_file_keeps_the_group(self):
        self.assertEqual(
            _fingerprint_server(_caught(_compiled_view(0))),
            _fingerprint_server(_caught(_compiled_view(7))),
        )

    def test_an_exception_never_raised_still_has_a_fingerprint(self):
        self.assertEqual(_fingerprint_server(KeyError('x')), _fingerprint_server(KeyError('y')))
