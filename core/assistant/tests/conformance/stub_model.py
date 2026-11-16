"""A stub of the OpenAI Chat Completions API that Janus talks to in the suite.

Janus always streams (``stream: true`` with ``stream_options.include_usage``), so
every answer goes out as server-sent events: content or tool-call deltas, a
``finish_reason``, then a last chunk with no choices that carries ``usage``.
Every path but ``POST /v1/chat/completions`` answers 404, which is also what
makes Janus's context-length probes (``/models``, ``/api/tags``, ``/v1/props``…)
fall back to its default instead of guessing a local server.

Answers are scripted per test, in order. A request past the end of the script is
answered "done" and recorded as unexpected, so a turn never hangs on the stub.
"""

from __future__ import annotations

import http.server
import json
import threading
from dataclasses import dataclass, field
from typing import Any

PROMPT_TOKENS = 100
COMPLETION_TOKENS = 10
SERVER_PREFIX = 'mcp_morpheus_admin_'


def store_tool(dotted: str) -> str:
    """The name Janus gives a store tool (``orders.search`` → ``mcp_morpheus_admin_orders_search``)."""
    return SERVER_PREFIX + ''.join(c if c.isalnum() or c == '_' else '_' for c in dotted)


@dataclass
class Answer:
    kind: str  # 'text' | 'tool_call' | 'empty' | 'error'
    text: str = ''
    tool: str = ''
    args: dict[str, Any] = field(default_factory=dict)
    status: int = 500


def text(value: str) -> Answer:
    return Answer('text', text=value)


def tool_call(tool: str, args: dict[str, Any] | None = None) -> Answer:
    """A call of ``tool``: a dotted store tool name, or a Janus tool's own name."""
    name = store_tool(tool) if '.' in tool else tool
    return Answer('tool_call', tool=name, args=args or {})


def empty() -> Answer:
    return Answer('empty')


def error(status: int = 500) -> Answer:
    return Answer('error', status=status)


class StubModel:
    """The server, its script and every request Janus sent."""

    def __init__(self) -> None:
        self.script: list[Answer] = []
        self.requests: list[dict[str, Any]] = []
        self.unexpected = 0
        self.other_paths: list[str] = []
        self._lock = threading.Lock()
        stub = self

        class Handler(http.server.BaseHTTPRequestHandler):
            protocol_version = 'HTTP/1.1'

            def do_POST(self):  # noqa: N802 — the stdlib's name
                length = int(self.headers.get('Content-Length') or 0)
                raw = self.rfile.read(length)
                if self.path.rstrip('/') != '/v1/chat/completions':
                    stub.other_paths.append(f'POST {self.path}')
                    return self._not_found()
                try:
                    body = json.loads(raw or b'{}')
                except ValueError:
                    body = {}
                stub._answer(self, body)

            def do_GET(self):  # noqa: N802
                stub.other_paths.append(f'GET {self.path}')
                self._not_found()

            def do_HEAD(self):  # noqa: N802
                stub.other_paths.append(f'HEAD {self.path}')
                self._not_found()

            def _not_found(self):
                payload = b'{"error": {"message": "not found"}}'
                self.send_response(404)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(payload)))
                self.end_headers()
                if self.command != 'HEAD':
                    self.wfile.write(payload)

            def log_message(self, *args):
                pass

        self.server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    @property
    def base_url(self) -> str:
        return f'http://127.0.0.1:{self.server.server_port}/v1'

    def start(self) -> StubModel:
        self.thread.start()
        return self

    def stop(self) -> None:
        self.server.shutdown()
        self.server.server_close()

    def load(self, *answers: Answer) -> None:
        with self._lock:
            self.script = list(answers)
            self.requests = []
            self.unexpected = 0
            self.other_paths = []

    # ── answering ────────────────────────────────────────────────────────────

    def _answer(self, handler, body: dict[str, Any]) -> None:
        with self._lock:
            self.requests.append(body)
            if self.script:
                answer = self.script.pop(0)
            else:
                self.unexpected += 1
                answer = text('done')
        if answer.kind == 'error':
            payload = json.dumps(
                {'error': {'message': 'stub server error', 'type': 'server_error'}}
            ).encode()
            handler.send_response(answer.status)
            handler.send_header('Content-Type', 'application/json')
            handler.send_header('Content-Length', str(len(payload)))
            handler.end_headers()
            handler.wfile.write(payload)
            return
        model = str(body.get('model') or 'stub')
        handler.send_response(200)
        handler.send_header('Content-Type', 'text/event-stream')
        handler.send_header('Cache-Control', 'no-cache')
        handler.send_header('Connection', 'close')
        handler.end_headers()
        for chunk in _chunks(answer, model):
            handler.wfile.write(f'data: {json.dumps(chunk)}\n\n'.encode())
        handler.wfile.write(b'data: [DONE]\n\n')
        handler.wfile.flush()
        handler.close_connection = True


def _chunk(model: str, delta: dict[str, Any] | None, finish: str | None = None) -> dict[str, Any]:
    choices = [] if delta is None else [{'index': 0, 'delta': delta, 'finish_reason': finish}]
    return {
        'id': 'chatcmpl-stub',
        'object': 'chat.completion.chunk',
        'created': 0,
        'model': model,
        'choices': choices,
    }


def _chunks(answer: Answer, model: str) -> list[dict[str, Any]]:
    out = [_chunk(model, {'role': 'assistant', 'content': ''})]
    if answer.kind == 'text':
        out.append(_chunk(model, {'content': answer.text}))
        out.append(_chunk(model, {}, 'stop'))
    elif answer.kind == 'tool_call':
        out.append(
            _chunk(
                model,
                {
                    'tool_calls': [
                        {
                            'index': 0,
                            'id': 'call_stub_1',
                            'type': 'function',
                            'function': {'name': answer.tool, 'arguments': json.dumps(answer.args)},
                        }
                    ]
                },
            )
        )
        out.append(_chunk(model, {}, 'tool_calls'))
    else:  # empty: nothing to say, nothing to call
        out.append(_chunk(model, {}, 'stop'))
    usage = _chunk(model, None)
    usage['usage'] = {
        'prompt_tokens': PROMPT_TOKENS,
        'completion_tokens': COMPLETION_TOKENS,
        'total_tokens': PROMPT_TOKENS + COMPLETION_TOKENS,
    }
    out.append(usage)
    return out
