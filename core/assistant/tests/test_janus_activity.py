"""Live steps: Janus's tool hooks write a line per step, the chat shows it.

Verified against Janus 0.18.0 on prod before this was built: ``pre_tool_call``
and ``post_tool_call`` fire for every tool, the agent-loop ones (``todo``)
included, and each hook run costs about 65 ms. The hook must never block a
call or fail a turn; the reader must never replay or half-read a line.
"""

from __future__ import annotations

import io
import json
import shlex
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from django.test import SimpleTestCase

from core.assistant import activity
from core.assistant import janus_progress_hook as hook


def _payload(event, tool, args=None, **extra):
    return {
        'hook_event_name': event,
        'tool_name': tool,
        'tool_input': args,
        'session_id': 's1',
        'cwd': '/tmp',
        'extra': extra,
    }


class HookScriptTests(SimpleTestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.path = Path(self._tmp.name) / 'progress.jsonl'

    def _run(self, payload) -> int:
        stdin = io.StringIO(payload if isinstance(payload, str) else json.dumps(payload))
        return hook.main(['hook', str(self.path)], stdin)

    def _lines(self) -> list[dict]:
        if not self.path.exists():
            return []
        return [json.loads(x) for x in self.path.read_text(encoding='utf-8').splitlines()]

    def test_one_line_per_step_start_and_end(self):
        self._run(_payload('pre_tool_call', 'web_search', {'query': 'tea'}, tool_call_id='c1'))
        self._run(
            _payload(
                'post_tool_call',
                'web_search',
                {'query': 'tea'},
                tool_call_id='c1',
                status='ok',
                duration_ms=812,
                result='{"data": "x"}',
            )
        )
        start, end = self._lines()
        self.assertEqual((start['ev'], start['tool'], start['id']), ('start', 'web_search', 'c1'))
        self.assertEqual(start['args'], {'query': 'tea'})
        self.assertEqual((end['ev'], end['status'], end['ms']), ('end', 'ok', 812))
        # A tool's output never lands in the file — only the plan's does.
        self.assertNotIn('result', end)

    def test_the_plan_keeps_its_full_result(self):
        result = json.dumps({'todos': [{'id': '1', 'content': 'Check stock', 'status': 'done'}]})
        self._run(_payload('post_tool_call', 'todo', {'merge': True}, status='ok', result=result))
        self.assertEqual(self._lines()[0]['result'], result)

    def test_long_arguments_are_clipped(self):
        self._run(
            _payload('pre_tool_call', 'mcp_morpheus_admin_seo_bulk_set_meta', {'x': 'y' * 9000})
        )
        line = self.path.read_text(encoding='utf-8')
        self.assertLess(len(line), 3000)

    def test_it_never_answers_so_it_can_never_block_a_call(self):
        out = io.StringIO()
        with mock.patch.object(sys, 'stdout', out):
            self._run(_payload('pre_tool_call', 'todo', {}))
        self.assertEqual(out.getvalue(), '')

    def test_garbage_and_other_events_are_ignored_quietly(self):
        for junk in ('not json', '[]', json.dumps(_payload('pre_llm_call', None))):
            self.assertEqual(self._run(junk), 0)
        self.assertEqual(self._lines(), [])

    def test_a_missing_path_argument_is_harmless(self):
        self.assertEqual(hook.main(['hook'], io.StringIO('{}')), 0)

    def test_it_imports_nothing_but_the_standard_library(self):
        # Janus runs it with `python -I -S`: no site-packages, no Django.
        source = Path(hook.__file__).read_text(encoding='utf-8')
        imports = {
            line.split()[1].split('.')[0]
            for line in source.splitlines()
            if line.startswith(('import ', 'from '))
        }
        self.assertLessEqual(imports, {'__future__', 'json', 'os', 'sys', 'time'})


class HooksConfigTests(SimpleTestCase):
    def test_both_tool_hooks_run_the_script_on_this_turns_file(self):
        block = activity.hooks_config(Path('/tmp/linda janus/conv/x/progress.jsonl'))
        self.assertIn('hooks_auto_accept: true', block)
        self.assertIn('  pre_tool_call:', block)
        self.assertIn('  post_tool_call:', block)
        command = json.loads(block.split('command: ', 1)[1].split('\n', 1)[0])
        argv = shlex.split(command)
        self.assertEqual(argv[0], sys.executable)
        self.assertIn('-I', argv)
        self.assertEqual(Path(argv[-2]), Path(hook.__file__))
        self.assertEqual(argv[-1], '/tmp/linda janus/conv/x/progress.jsonl')
        self.assertIn('timeout: 5', block)


class ReaderTests(SimpleTestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.path = Path(self._tmp.name) / 'progress.jsonl'
        self.reader = activity.ProgressReader(self.path)
        self.reader.reset()

    def _write(self, *records, partial=''):
        with self.path.open('a', encoding='utf-8') as fh:
            for rec in records:
                fh.write(json.dumps(rec) + '\n')
            fh.write(partial)

    def test_reset_empties_the_file_from_the_last_turn(self):
        self._write({'ev': 'start', 'tool': 'web_search', 'id': 'old'})
        reader = activity.ProgressReader(self.path)
        reader.reset()
        self.assertEqual(reader.read(), [])

    def test_steps_start_then_finish(self):
        self._write({'ev': 'start', 'tool': 'web_search', 'id': 'c1', 'args': {'query': 'tea'}})
        (started,) = self.reader.read()
        self.assertEqual((started['type'], started['state']), ('step', 'running'))
        self.assertEqual(started['label'], 'Searching the web')
        self.assertEqual(started['detail'], 'tea')
        self._write({'ev': 'end', 'tool': 'web_search', 'id': 'c1', 'status': 'ok', 'ms': 900})
        (done,) = self.reader.read()
        self.assertEqual((done['id'], done['state'], done['ms']), (started['id'], 'done', 900))
        self.assertEqual(done['done_label'], 'Searched the web')

    def test_a_failed_step_says_so(self):
        self._write(
            {'ev': 'start', 'tool': 'web_search', 'id': 'c1'},
            {'ev': 'end', 'tool': 'web_search', 'id': 'c1', 'status': 'error', 'error': 'boom'},
        )
        _, done = self.reader.read()
        self.assertEqual(done['state'], 'error')

    def test_a_half_written_line_waits_for_its_end(self):
        self._write(partial='{"ev": "start", "tool": "web_')
        self.assertEqual(self.reader.read(), [])
        self._write(partial='search", "id": "c1"}\n')
        (step,) = self.reader.read()
        self.assertEqual(step['tool'], 'web_search')

    def test_nothing_is_replayed(self):
        self._write({'ev': 'start', 'tool': 'web_search', 'id': 'c1'})
        self.assertEqual(len(self.reader.read()), 1)
        self.assertEqual(self.reader.read(), [])

    def test_a_missing_file_reads_as_no_news(self):
        reader = activity.ProgressReader(Path(self._tmp.name) / 'none' / 'progress.jsonl')
        self.assertEqual(reader.read(), [])

    def test_the_plan_is_the_todo_tools_full_list(self):
        result = json.dumps(
            {
                'todos': [
                    {'id': '1', 'content': 'Pull last month’s orders', 'status': 'completed'},
                    {
                        'id': '2',
                        'content': 'Compare with the month before',
                        'status': 'in_progress',
                    },
                ]
            }
        )
        self._write(
            {'ev': 'start', 'tool': 'todo', 'id': 't1', 'args': {'merge': True}},
            {'ev': 'end', 'tool': 'todo', 'id': 't1', 'status': 'ok', 'result': result},
        )
        (plan,) = self.reader.read()
        self.assertEqual(plan['type'], 'plan')
        self.assertEqual(
            plan['items'],
            [
                {'id': '1', 'text': 'Pull last month’s orders', 'status': 'completed'},
                {'id': '2', 'text': 'Compare with the month before', 'status': 'in_progress'},
            ],
        )

    def test_store_tools_name_the_area_and_whether_they_change_it(self):
        from core.agents.tools import Tool

        read = Tool(
            name='orders.search',
            description='d',
            handler=lambda **kw: None,
            scopes=['orders.read'],
            schema={},
        )
        write = Tool(
            name='gift_cards.issue',
            description='d',
            handler=lambda **kw: None,
            scopes=['gift_cards.write'],
            schema={},
        )
        with mock.patch.object(activity, '_store_tools', return_value=[read, write]):
            reader = activity.ProgressReader(self.path)
            self._write(
                {'ev': 'start', 'tool': 'mcp_morpheus_admin_orders_search', 'id': 'a'},
                {'ev': 'start', 'tool': 'mcp_morpheus_admin_gift_cards_issue', 'id': 'b'},
            )
            first, second = reader.read()
        self.assertEqual(
            (first['label'], first['store_tool']), ('Checking orders', 'orders.search')
        )
        self.assertEqual(first['detail'], 'search')
        self.assertEqual(second['label'], 'Updating gift cards')
        self.assertEqual(second['store_tool'], 'gift_cards.issue')

    def test_unknown_tools_still_show_up(self):
        self._write(
            {'ev': 'start', 'tool': 'skill_view', 'id': 'k', 'args': {'name': 'morpheus-orders'}}
        )
        (step,) = self.reader.read()
        self.assertEqual(step['label'], 'Reading a playbook')
        self.assertEqual(step['detail'], 'morpheus-orders')
        self._write({'ev': 'start', 'tool': 'brand_new_tool', 'id': 'z'})
        (step,) = self.reader.read()
        self.assertEqual(step['label'], 'Brand new tool')

    def test_end_without_an_id_closes_the_oldest_open_step_of_that_tool(self):
        self._write(
            {'ev': 'start', 'tool': 'web_search', 'id': ''},
            {'ev': 'end', 'tool': 'web_search', 'id': '', 'status': 'ok', 'ms': 5},
        )
        started, done = self.reader.read()
        self.assertEqual(started['id'], done['id'])
