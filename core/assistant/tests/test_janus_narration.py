"""Linda says what she is about to do, and the chat shows it while she works.

Janus's Telegram gateway feels alive because the model's words between tool
calls reach the chat ("Checking stock first…"), and a provider hiccup shows as a
retry instead of silence. The subprocess never printed either. Janus fires
``post_api_request`` after every model call (the words, the tool-call count and
the token use) and ``api_request_error`` when a call fails, so the progress hook
subscribes to both and the chat streams them as ``say``, ``usage`` and ``retry``.
"""

from __future__ import annotations

import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from django.test import SimpleTestCase

from core.assistant import activity, janus_contract
from core.assistant import janus_progress_hook as hook


def _api_call(content, tool_calls=1, total=1200, **usage):
    return {
        'hook_event_name': 'post_api_request',
        'tool_name': None,
        'tool_input': None,
        'session_id': 's1',
        'cwd': '/tmp',
        'extra': {
            'api_call_count': 1,
            'assistant_tool_call_count': tool_calls,
            'response': {'assistant_message': {'role': 'assistant', 'content': content}},
            'usage': {'input_tokens': 1000, 'output_tokens': 200, 'total_tokens': total, **usage},
            'request': {'body': {'messages': ['…the whole conversation…']}},
        },
    }


def _api_error(status=503, retry=1, retryable=True):
    return {
        'hook_event_name': 'api_request_error',
        'tool_name': None,
        'tool_input': None,
        'extra': {
            'status_code': status,
            'retry_count': retry,
            'max_retries': 1,
            'retryable': retryable,
            'error': {'type': 'APIError', 'message': 'Incorrect API key provided: sk-abc…xyz'},
        },
    }


class _HookCase(SimpleTestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.path = Path(self._tmp.name) / 'progress.jsonl'

    def _run(self, payload):
        return hook.main(['hook', str(self.path)], io.StringIO(json.dumps(payload)))

    def _lines(self):
        if not self.path.exists():
            return []
        return [json.loads(x) for x in self.path.read_text(encoding='utf-8').splitlines()]


class HookNarrationTests(_HookCase):
    def test_the_words_before_a_tool_call_are_kept_with_the_token_use(self):
        self._run(_api_call('Checking stock before I suggest a reorder.'))
        (line,) = self._lines()
        self.assertEqual(line['ev'], 'call')
        self.assertEqual(line['text'], 'Checking stock before I suggest a reorder.')
        self.assertEqual(line['tokens'], 1200)
        # The conversation the request carried never lands in the file.
        self.assertNotIn('conversation', json.dumps(line))

    def test_the_final_answer_is_not_narration(self):
        # The answer reaches the chat the normal way; only its tokens count here.
        self._run(_api_call('Here is your report…', tool_calls=0))
        (line,) = self._lines()
        self.assertEqual(line['text'], '')
        self.assertEqual(line['tokens'], 1200)

    def test_thinking_tags_are_not_shown_as_words(self):
        self._run(_api_call('<think>The merchant wants…</think>Looking at last week first.'))
        self.assertEqual(self._lines()[0]['text'], 'Looking at last week first.')

    def test_a_long_narration_is_clipped(self):
        self._run(_api_call('x' * 5000))
        self.assertLessEqual(len(self._lines()[0]['text']), 600)

    def test_a_provider_error_records_the_status_never_its_text(self):
        self._run(_api_error())
        (line,) = self._lines()
        self.assertEqual((line['ev'], line['status'], line['retry']), ('retry', 503, True))
        self.assertNotIn('sk-', json.dumps(line))


class ReaderNarrationTests(SimpleTestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.path = Path(self._tmp.name) / 'progress.jsonl'
        self.reader = activity.ProgressReader(self.path)
        self.reader.reset()

    def _write(self, *records):
        with self.path.open('a', encoding='utf-8') as fh:
            for rec in records:
                fh.write(json.dumps(rec) + '\n')

    def test_words_become_a_say_event_and_tokens_add_up(self):
        self._write(
            {'t': 1, 'ev': 'call', 'text': 'Checking stock first.', 'tools': 2, 'tokens': 1200},
            {'t': 2, 'ev': 'call', 'text': '', 'tools': 0, 'tokens': 800},
        )
        events = self.reader.read()
        says = [e for e in events if e['type'] == 'say']
        usage = [e for e in events if e['type'] == 'usage']
        self.assertEqual([s['text'] for s in says], ['Checking stock first.'])
        self.assertEqual([(u['tokens'], u['calls']) for u in usage], [(1200, 1), (2000, 2)])

    def test_a_retry_says_whether_another_try_follows(self):
        self._write({'t': 1, 'ev': 'retry', 'status': 429, 'retry': True})
        (event,) = self.reader.read()
        self.assertEqual(event, {'type': 'retry', 'status': 429, 'retrying': True})


class HookWiringTests(SimpleTestCase):
    def test_the_config_subscribes_every_event_the_chat_reads(self):
        block = activity.hooks_config(Path('/tmp/progress.jsonl'))
        for event in activity.HOOK_EVENTS:
            self.assertIn(f'  {event}:', block)
        self.assertIn('post_api_request', activity.HOOK_EVENTS)
        self.assertIn('api_request_error', activity.HOOK_EVENTS)

    def test_the_contract_checks_the_same_events(self):
        # An auto-updated Janus that drops one of them must fail the contract.
        self.assertEqual(set(janus_contract.HOOK_EVENTS), set(activity.HOOK_EVENTS))


class QuestionStepLabelTests(SimpleTestCase):
    def test_the_question_step_says_she_is_asking(self):
        from unittest import mock

        from core.agents.tools import Tool

        ask = Tool(
            name='assistant.ask',
            description='d',
            handler=lambda **kw: None,
            scopes=['system.read'],
            schema={},
        )
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / 'progress.jsonl'
            path.write_text(
                json.dumps({'ev': 'start', 'tool': 'mcp_morpheus_admin_assistant_ask', 'id': 'q'})
                + '\n'
            )
            with mock.patch.object(activity, '_store_tools', return_value=[ask]):
                (step,) = activity.ProgressReader(path).read()
        self.assertEqual(
            (step['label'], step['store_tool']), ('Asking you a question', 'assistant.ask')
        )
