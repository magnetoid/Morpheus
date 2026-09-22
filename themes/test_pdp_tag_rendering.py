"""Every theme's PDP renders string tags without 500ing.

The GraphQL Product ``tags`` field returns a list of plain strings
(``catalog/graphql/types.py`` -> ``[t.name for t in self.tags.all()]``), so in
the PDP template ``tag`` is a ``str`` like ``'divination'`` — never an object
with ``.slug``/``.name``. The original ``{{ tag.slug|default:tag.name }}`` blew
up on exactly that: a filter *argument* (``default:tag.name``) is resolved
eagerly and RAISES ``VariableDoesNotExist`` instead of failing silently, so
every product carrying a tag 500'd its PDP (180 of 684 live products on the
supernatural store) while tagless products rendered fine. ``{% firstof %}``
resolves each candidate with ``ignore_failures=True``, so it degrades to the
bare string. Guards the django-default-filter-eager-arg landmine at the theme
layer.
"""

from __future__ import annotations

import pathlib
import re

from django.conf import settings
from django.template import Context, Template
from django.test import SimpleTestCase

_TAG_LOOP = re.compile(r"{% for tag in product\.tags %}.*?{% endfor %}", re.S)


class PdpStringTagRenderingTests(SimpleTestCase):
    def test_every_theme_pdp_renders_a_string_tag(self):
        root = pathlib.Path(settings.BASE_DIR) / "themes" / "library"
        pdps = sorted(root.glob("*/templates/storefront/product_detail.html"))
        tested = 0
        for pdp in pdps:
            m = _TAG_LOOP.search(pdp.read_text())
            if not m:  # a theme without a tag chip loop is fine
                continue
            tested += 1
            theme = pdp.relative_to(root).parts[0]
            # product.tags is a list of STRINGS, exactly as GraphQL returns it.
            ctx = Context({"product": {"tags": ["divination"]}})
            out = Template(m.group(0)).render(ctx)  # raised on the old template
            self.assertIn(
                "divination", out, f"{theme}: string tag dropped from the chip"
            )
            self.assertIn(
                "?tag=divination", out, f"{theme}: tag link lost its query value"
            )
        # Don't let the guard pass vacuously if the glob or regex drifts.
        self.assertGreaterEqual(tested, 3, "expected the 3 shipped themes to have a tag loop")
