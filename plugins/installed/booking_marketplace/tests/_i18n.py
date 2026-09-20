"""Enable Serbian for the tests that assert on translated storefront copy.

`LANGUAGES` is built from the `MORPHEUS_LANGUAGES` env var and defaults to the
core language ALONE, so on a default run `settings.LANGUAGES == [('en', …)]`.
`LocaleMiddleware` can then never activate `sr` whatever `Accept-Language` says,
and these tests assert on English while looking like a translation bug — which
is how they arrived from montenegro-new already red.

The Serbian catalog itself ships in the tree (locale/sr/LC_MESSAGES/django.mo),
so the only thing missing in tests is the opt-in. Declaring it here rather than
relying on a deployment env var keeps the suite honest on any machine: the live
Montenegro store sets MORPHEUS_LANGUAGES=en,sr, and a store that does not simply
serves English.
"""

from __future__ import annotations

from django.test import override_settings

SERBIAN = ('sr', 'Српски')


def serbian_enabled(cls):
    """Class decorator: add `sr` to LANGUAGES for the decorated TestCase."""
    return override_settings(LANGUAGES=[('en', 'English'), SERBIAN])(cls)
