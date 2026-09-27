"""Tool.invoke argument forwarding.

``invoke`` forwards only the arguments a handler can take, so a typo'd or
undeclared argument never reaches it. A handler written as ``def h(*, slug,
**fields)`` names only ``slug``, so the filter dropped EVERY other argument:
``catalog.update_product``, ``catalog.update_variant``, ``catalog.create_product``,
``catalog.create_variant`` and ``seo.set_site_settings`` ran as silent no-ops and
reported success ("Updated … — fields: []") while nothing changed.
"""

from __future__ import annotations

from django.test import SimpleTestCase

from core.agents.tools import Tool


def _kwargs_tool(received: list) -> Tool:
    def handler(*, slug: str, context=None, **fields):
        received.append({'slug': slug, 'context': context, **fields})
        return {'ok': True}

    return Tool(
        name='thing.update',
        description='d',
        handler=handler,
        schema={
            'type': 'object',
            'properties': {
                'slug': {'type': 'string'},
                'name': {'type': 'string'},
                'is_featured': {'type': 'boolean'},
            },
            'required': ['slug'],
        },
    )


class KwargsHandlerForwardingTests(SimpleTestCase):
    def test_schema_declared_arguments_reach_a_kwargs_handler(self):
        received: list = []
        _kwargs_tool(received).invoke({'slug': 'a', 'name': 'New', 'is_featured': True})
        self.assertEqual(received[0]['name'], 'New')
        self.assertIs(received[0]['is_featured'], True)

    def test_undeclared_arguments_are_still_dropped(self):
        # The filter's purpose stands: what the schema does not declare (a
        # model's habitual `confirmed=True`, a typo) never reaches the handler.
        received: list = []
        _kwargs_tool(received).invoke({'slug': 'a', 'confirmed': True, 'nmae': 'x'})
        self.assertNotIn('confirmed', received[0])
        self.assertNotIn('nmae', received[0])

    def test_runtime_context_is_never_taken_from_the_arguments(self):
        received: list = []
        _kwargs_tool(received).invoke(
            {'slug': 'a', 'context': {'staged': True}}, context={'source': 'mcp'}
        )
        self.assertEqual(received[0]['context'], {'source': 'mcp'})
