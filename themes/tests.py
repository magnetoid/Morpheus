"""Theme engine tests: base validation + scaffolder."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase

from themes.base import MorpheusTheme, ThemeConfigurationError


class ThemeMetadataValidationTests(SimpleTestCase):
    def test_valid_subclass(self):
        class Good(MorpheusTheme):
            name = 'good_theme'
            label = 'Good Theme'
            version = '1.2.3'

        self.assertEqual(Good.name, 'good_theme')

    def test_invalid_name_camel(self):
        with self.assertRaises(ThemeConfigurationError):

            class Bad(MorpheusTheme):
                name = 'BadTheme'
                label = 'X'
                version = '1.0.0'

    def test_missing_label(self):
        with self.assertRaises(ThemeConfigurationError):

            class NoLabel(MorpheusTheme):
                name = 'no_label_theme'
                label = ''
                version = '1.0.0'

    def test_invalid_version(self):
        with self.assertRaises(ThemeConfigurationError):

            class BadVer(MorpheusTheme):
                name = 'bad_ver_theme'
                label = 'Bad Ver'
                version = 'oops'

    def test_supports_plugins_must_be_list_of_strings(self):
        with self.assertRaises(ThemeConfigurationError):

            class BadSupports(MorpheusTheme):
                name = 'bad_supports_theme'
                label = 'Bad Supports'
                version = '1.0.0'
                supports_plugins = ['ok', 7]  # type: ignore


class MorphCreateThemeTests(SimpleTestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix='morph-theme-'))

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _scaffold(self, name: str, **flags) -> Path:
        call_command('morph_create_theme', name, target=str(self.tmp), **flags)
        return self.tmp / name

    def test_minimal_scaffold(self):
        out = self._scaffold('starter')
        self.assertTrue((out / 'theme.py').exists())
        self.assertTrue((out / 'README.md').exists())
        self.assertTrue((out / 'templates/storefront/base.html').exists())
        self.assertTrue((out / 'templates/storefront/home.html').exists())
        self.assertTrue((out / 'templates/storefront/product_list.html').exists())
        self.assertTrue((out / 'templates/storefront/product_detail.html').exists())
        self.assertTrue((out / 'templates/storefront/cart.html').exists())
        self.assertTrue((out / 'templates/storefront/checkout.html').exists())
        self.assertTrue((out / 'static/starter/style.css').exists())

    def test_theme_py_compiles_and_declares_class(self):
        out = self._scaffold('compile_theme', label='Compile Theme', theme_version='0.2.0')
        body = (out / 'theme.py').read_text()
        compile(body, str(out / 'theme.py'), 'exec')
        self.assertIn('class CompileThemeTheme(MorpheusTheme):', body)
        self.assertIn('"compile_theme"', body)
        self.assertIn('"0.2.0"', body)

    def test_rejects_bad_name(self):
        with self.assertRaises(CommandError):
            call_command('morph_create_theme', 'BadName', target=str(self.tmp))

    def test_refuses_to_overwrite(self):
        self._scaffold('again')
        with self.assertRaises(CommandError):
            call_command('morph_create_theme', 'again', target=str(self.tmp))


class RegistryValidationTests(SimpleTestCase):
    def test_validate_returns_error_when_no_active(self):
        from themes.registry import ThemeRegistry

        r = ThemeRegistry()
        errors = r.validate_active_theme()
        self.assertTrue(errors)


class DotBooksThemeTests(SimpleTestCase):
    def test_dot_books_passes_validation(self):
        from themes.library.dot_books.theme import DotBooksTheme

        # Re-import + instantiate; should not raise.
        theme = DotBooksTheme()
        self.assertEqual(theme.name, 'dot_books')
        # design tokens / config schema are well-formed dicts
        self.assertIsInstance(theme.get_config_schema(), dict)
