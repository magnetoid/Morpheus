"""richtext plugin — Lexical editor as a self-hosted app."""

from django.template import Context, Template
from django.test import SimpleTestCase, TestCase


class RichTextPluginContractTests(SimpleTestCase):
    def test_plugin_registered_and_active(self):
        from plugins.registry import app_registry

        self.assertTrue(app_registry.is_active('richtext'))
        plugin = app_registry.get('richtext')
        self.assertIsNotNone(plugin)
        self.assertEqual(plugin.name, 'richtext')


def _render(*, value='', **kwargs):
    # `value` is passed as a context VARIABLE (not a template literal) so it
    # autoescapes exactly as it does in real forms — Django treats inline
    # template string literals as safe, which would mask the escaping.
    args = ' '.join(f'{k}={v!r}' if isinstance(v, str) else f'{k}={v}' for k, v in kwargs.items())
    tpl = Template('{% load richtext %}{% richtext_field value=val ' + args + ' %}')
    return tpl.render(Context({'val': value}))


class RichTextFieldTagTests(TestCase):
    def test_active_renders_editor_markup(self):
        html = _render(
            name='description',
            value='<p>hi</p>',
            id='product-description',
            allow_headings=True,
            allow_images=False,
            expose_as='morphProductDescriptionEditor',
            aria_label='Product description',
        )
        self.assertIn('data-richtext', html)
        self.assertIn('data-rte-mount', html)
        self.assertIn('data-allow-headings="true"', html)
        self.assertIn('data-allow-images="false"', html)
        self.assertIn('data-expose-as="morphProductDescriptionEditor"', html)
        self.assertIn('/dashboard/media/api/upload/', html)
        self.assertIn('name="description"', html)
        self.assertIn('id="product-description"', html)
        self.assertIn('&lt;p&gt;hi&lt;/p&gt;', html)  # value escaped inside textarea

    def test_image_button_only_when_allowed(self):
        with_img = _render(name='body', value='', allow_images=True)
        without = _render(name='description', value='', allow_images=False)
        self.assertIn('data-rte="image"', with_img)
        self.assertNotIn('data-rte="image"', without)

    def test_heading_buttons_only_when_allowed(self):
        with_h = _render(name='body', value='', allow_headings=True)
        without = _render(name='short_description', value='', allow_headings=False)
        self.assertIn('data-rte="h2"', with_h)
        self.assertNotIn('data-rte="h2"', without)

    def test_degrades_to_textarea_when_plugin_inactive(self):
        from plugins.registry import app_registry

        original = app_registry.is_active
        app_registry.is_active = lambda n: False if n == 'richtext' else original(n)
        try:
            html = _render(name='description', value='<p>x</p>', id='product-description')
        finally:
            app_registry.is_active = original
        self.assertNotIn('data-richtext', html)
        self.assertIn('name="description"', html)
        self.assertIn('id="product-description"', html)
        self.assertIn('&lt;p&gt;x&lt;/p&gt;', html)
