"""Generic translation API surface (MCP tools + GraphQL extension classes) that
lets external translators read/write translations for any object."""

from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from core.agents import ToolError
from core.i18n.agent_tools import (
    get_translations_tool,
    list_languages_tool,
    set_translation_tool,
)
from core.models import StoreSettings


def _ct_str(model) -> str:
    ct = ContentType.objects.get_for_model(model)
    return f'{ct.app_label}.{ct.model}'


class GenericMcpToolTests(TestCase):
    def setUp(self):
        self.obj = StoreSettings.objects.create(store_name='Shop')
        self.ct = _ct_str(StoreSettings)

    def test_set_then_get_roundtrip(self):
        res = set_translation_tool.handler(
            content_type=self.ct,
            object_id=str(self.obj.pk),
            field='store_name',
            language_code='fr',
            value='Boutique',
        )
        self.assertEqual(res.output['language'], 'fr')

        got = get_translations_tool.handler(content_type=self.ct, object_id=str(self.obj.pk))
        self.assertEqual(got.output['translations'].get('store_name@fr'), 'Boutique')

    def test_get_filtered_by_language(self):
        set_translation_tool.handler(
            content_type=self.ct,
            object_id=str(self.obj.pk),
            field='store_name',
            language_code='fr',
            value='Boutique',
        )
        set_translation_tool.handler(
            content_type=self.ct,
            object_id=str(self.obj.pk),
            field='store_name',
            language_code='de',
            value='Laden',
        )
        got = get_translations_tool.handler(
            content_type=self.ct, object_id=str(self.obj.pk), language_code='de'
        )
        keys = got.output['translations'].keys()
        self.assertIn('store_name@de', keys)
        self.assertNotIn('store_name@fr', keys)

    def test_unknown_content_type_raises(self):
        with self.assertRaises(ToolError):
            get_translations_tool.handler(content_type='nope.nothing', object_id='1')

    def test_missing_object_raises(self):
        with self.assertRaises(ToolError):
            set_translation_tool.handler(
                content_type=self.ct,
                object_id='999999',
                field='store_name',
                language_code='fr',
                value='x',
            )

    def test_languages_tool(self):
        res = list_languages_tool.handler()
        self.assertIn('languages', res.output)
        self.assertIsInstance(res.output['languages'], list)

    def test_tools_carry_i18n_scopes(self):
        self.assertEqual(set_translation_tool.scopes, ['i18n.write'])
        self.assertEqual(get_translations_tool.scopes, ['i18n.read'])
        self.assertTrue(set_translation_tool.requires_approval)


class GraphQLExtensionTests(TestCase):
    def test_extension_classes_define_fields(self):
        # Import the modules the localization plugin registers; confirm the
        # resolver methods exist (schema assembly discovers *QueryExtension /
        # *MutationExtension by name).
        from plugins.installed.localization.graphql.mutations import (
            LocalizationMutationExtension,
        )
        from plugins.installed.localization.graphql.queries import (
            LocalizationQueryExtension,
        )

        self.assertTrue(hasattr(LocalizationQueryExtension, 'enabled_languages'))
        self.assertTrue(hasattr(LocalizationQueryExtension, 'translations'))
        self.assertTrue(hasattr(LocalizationMutationExtension, 'set_translation'))

    def test_i18n_scopes_registered(self):
        from plugins.installed.agent_mcp.scopes import AVAILABLE_SCOPES

        self.assertIn('i18n.read', AVAILABLE_SCOPES)
        self.assertIn('i18n.write', AVAILABLE_SCOPES)
