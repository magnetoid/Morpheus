"""The run_python validator refuses the interpreter's frame and code attributes.

Dunder attributes were refused, but generator, frame, traceback and code objects
carry plain-named attributes (`gi_frame`, `f_back`, `tb_frame`, `co_code`, …) that
lead out of the curated namespace. These tests only parse source text: nothing
in them runs.
"""

from __future__ import annotations

import ast

from django.test import SimpleTestCase

from core.agents.sandbox import SandboxError, _validate, run_sandboxed


def _check(source: str) -> None:
    _validate(ast.parse(source, mode='exec'))


class FrameAttributeTests(SimpleTestCase):
    def test_refuses_frame_and_code_attributes(self):
        for attr in (
            'gi_frame',
            'gi_code',
            'f_back',
            'f_globals',
            'tb_frame',
            'cr_frame',
            'ag_frame',
            'co_code',
            'func_globals',
        ):
            with self.subTest(attr=attr), self.assertRaises(SandboxError):
                _check(f'result = thing.{attr}')

    def test_refuses_str_format_which_reads_attributes_from_text(self):
        for source in ("result = '{0.real}'.format(1)", "result = '{x}'.format_map({'x': 1})"):
            with self.subTest(source=source), self.assertRaises(SandboxError):
                _check(source)
        _check("x = 1\nresult = f'{x.real}'")  # an f-string is parsed, so it is checked

    def test_refuses_them_when_assigned_too(self):
        with self.assertRaises(SandboxError):
            _check('thing.f_locals = {}')

    def test_still_runs_ordinary_scripts(self):
        self.assertEqual(run_sandboxed('result = sum(x * 2 for x in range(4))'), 12)
        self.assertEqual(
            run_sandboxed('f_total = 3\nco_owner = "x"\nresult = (f_total, co_owner)'),
            (3, 'x'),
        )

    def test_attribute_names_that_only_contain_the_letters_pass(self):
        out = run_sandboxed(
            'result = [d.items() for d in [{"a": 1}]][0]',
        )
        self.assertEqual(list(out), [('a', 1)])
        _check('result = order.coffee_total + order.af_fee + order.total_f_')
