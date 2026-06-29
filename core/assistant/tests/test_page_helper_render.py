from django.template import Context, Template
from django.test import TestCase


class PageHelperRenderTests(TestCase):
    def test_partial_renders_container_and_endpoint(self):
        html = Template('{% include "assistant/_page_helper.html" %}').render(Context({}))
        self.assertIn('id="linda-page-helper"', html)
        self.assertIn('/dashboard/assistant/page-help/', html)
