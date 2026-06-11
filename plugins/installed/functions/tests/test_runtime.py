"""Sandbox runtime tests."""

from __future__ import annotations

from django.test import TestCase

from plugins.installed.functions.runtime import (
    FunctionError,
    FunctionExecutionError,
    execute,
)


class FunctionsRuntimeTests(TestCase):
    def test_simple_function(self):
        result = execute(
            source='def run(input): return input["x"] * 2',
            input={'x': 21},
        )
        self.assertEqual(result.output, 42)

    def test_must_define_run(self):
        with self.assertRaises(FunctionExecutionError):
            execute(source='x = 1', input={})

    def test_rejects_import(self):
        with self.assertRaises(FunctionError):
            execute(source='import os\ndef run(input): return 1', input={})

    def test_rejects_dunder_access(self):
        with self.assertRaises(FunctionError):
            execute(
                source='def run(input): return (1).__class__.__bases__',
                input={},
            )

    def test_rejects_open_builtin(self):
        with self.assertRaises(FunctionError):
            execute(source='def run(input): return open("/etc/passwd")', input={})

    def test_capability_grant_math(self):
        result = execute(
            source='def run(input): return floor(sqrt(input["x"]))',
            input={'x': 17},
            capabilities=['math'],
        )
        self.assertEqual(result.output, 4)

    def test_unknown_capability(self):
        with self.assertRaises(FunctionError):
            execute(source='def run(input): return 1', capabilities=['nonexistent'])

    def test_runtime_errors_are_wrapped(self):
        with self.assertRaises(FunctionExecutionError):
            execute(source='def run(input): return input["missing"]', input={})

    def test_oversized_source_rejected(self):
        with self.assertRaises(FunctionError):
            execute(source='def run(input): return 1\n' + ('# x' * 10000), input={})


class FunctionsDispatchTests(TestCase):
    """Verify dispatch_filter wires through to enabled rows."""

    def test_dispatch_filter_with_no_rows_returns_value_unchanged(self):
        from plugins.installed.functions.services import dispatch_filter

        out = dispatch_filter(target='cart.calculate_total', value=100, input={'value': '100'})
        self.assertEqual(out, 100)

    def test_dispatch_filter_pipes_value_through_function(self):
        from djmoney.money import Money

        from plugins.installed.functions.models import Function
        from plugins.installed.functions.services import dispatch_filter

        Function.objects.create(
            target='cart.calculate_total',
            name='ten-percent-off',
            source=('def run(input):\n    return float(input["value"]) * 0.9\n'),
            capabilities=[],
            is_enabled=True,
        )
        out = dispatch_filter(
            target='cart.calculate_total',
            value=Money(100, 'USD'),
            input={'value': '100', 'currency': 'USD'},
        )
        self.assertEqual(out.amount, Money(90, 'USD').amount)
