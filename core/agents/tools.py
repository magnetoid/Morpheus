"""
Agent tools — the unit a `MorpheusAgent` actually calls.

A `Tool` is a callable plus enough metadata for an LLM to use it: a JSON
Schema for arguments, a description, and a list of *scopes* (capability
strings the agent must hold). Tools are pure Python functions; we keep
them out of GraphQL so plugin authors can write them without touching
Strawberry.

Decorator usage::

    from core.agents import tool

    @tool(
        name='catalog.find_products',
        description='Search products by free-text query.',
        scopes=['catalog.read'],
        schema={
            'type': 'object',
            'properties': {
                'query': {'type': 'string'},
                'limit': {'type': 'integer', 'minimum': 1, 'maximum': 50},
            },
            'required': ['query'],
        },
    )
    def find_products(*, query: str, limit: int = 10) -> dict:
        ...
        return {'products': [...]}

The decorator returns a `Tool` instance ready to be returned from
`MorpheusPlugin.contribute_agent_tools()`.
"""

from __future__ import annotations

import inspect
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger('morpheus.agents.tools')


class ToolError(RuntimeError):
    """Raised by a tool to surface a clean, LLM-readable failure."""


@dataclass(slots=True)
class ToolResult:
    """The structured output of a tool call.

    `output` is what gets serialized back to the LLM. `display` is an
    optional human-readable summary (used in dashboards / chat UI).
    `metadata` is internal — never sent to the LLM.
    """

    output: Any
    display: str = ''
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Tool:
    """A single capability an agent can invoke.

    `scopes` is the contract: an agent must have *all* of these scopes to
    call this tool. The runtime checks scopes before invocation; the
    LLM never sees a tool it cannot call.
    """

    name: str
    description: str
    handler: Callable[..., Any]
    schema: dict[str, Any] = field(default_factory=dict)
    scopes: list[str] = field(default_factory=list)
    requires_approval: bool = False
    # True only for tools that implement staged mode (record an OpsProposal
    # instead of executing when context['staged'] is set). The runtime uses
    # this to scope the staged approval-gate exemption: a tool WITHOUT a
    # staging path must NOT be exempted, or it would execute directly with
    # zero approval under staged context (hunt #5 / audit S1 regression).
    supports_staging: bool = False
    plugin: str = ''

    @property
    def api_name(self) -> str:
        """Provider-safe spelling of `name`.

        OpenAI and Anthropic both enforce ``^[a-zA-Z0-9_-]+$`` on tool
        names, so the canonical dotted names (``orders.update_status``)
        are sent with dots mapped to ``__``. Runtimes index tools under
        BOTH spellings, so a model calling ``orders__update_status``
        resolves to the same tool. (Anthropic 400s outright on a dotted
        name: "String should match pattern '^[a-zA-Z0-9_-]{1,128}$'".)
        """
        return self.name.replace('.', '__')

    def to_openai_schema(self) -> dict[str, Any]:
        """Render this tool as an OpenAI function-calling spec."""
        return {
            'type': 'function',
            'function': {
                'name': self.api_name,
                'description': self.description,
                'parameters': self.schema or {'type': 'object', 'properties': {}},
            },
        }

    def to_anthropic_schema(self) -> dict[str, Any]:
        """Render this tool as an Anthropic tool-use spec."""
        return {
            'name': self.api_name,
            'description': self.description,
            'input_schema': self.schema or {'type': 'object', 'properties': {}},
        }

    def invoke(self, arguments: dict[str, Any], **runtime_kwargs: Any) -> ToolResult:
        """Call the underlying handler, normalising the return type."""
        sig = inspect.signature(self.handler)
        params = sig.parameters
        runtime_names = ('agent', 'request', 'context', 'customer')
        # A `**fields` handler names only some of its arguments; the rest are
        # the ones its schema declares. Filtering on the signature alone dropped
        # them all, so catalog.update_product & co. reported success and changed
        # nothing. Undeclared arguments (typos, a habitual `confirmed=True`) are
        # still dropped, and runtime context never comes from the model.
        takes_kwargs = any(p.kind is inspect.Parameter.VAR_KEYWORD for p in params.values())
        declared = set(((self.schema or {}).get('properties') or {}).keys())
        accepted: dict[str, Any] = {}
        for k, v in (arguments or {}).items():
            if k in runtime_names:
                continue
            named = k in params and params[k].kind not in (
                inspect.Parameter.VAR_KEYWORD,
                inspect.Parameter.VAR_POSITIONAL,
            )
            if named or (takes_kwargs and k in declared):
                accepted[k] = v
        # Inject runtime context if the handler asks for it.
        for ctx_name in runtime_names:
            if ctx_name in params and ctx_name in runtime_kwargs:
                accepted[ctx_name] = runtime_kwargs[ctx_name]
        try:
            out = self.handler(**accepted)
        except ToolError:
            raise
        except Exception as e:  # noqa: BLE001
            logger.warning('tool %s raised: %s', self.name, e, exc_info=True)
            raise ToolError(f'{type(e).__name__}: {e}') from e

        if isinstance(out, ToolResult):
            return out
        return ToolResult(output=out)


def tool(
    *,
    name: str,
    description: str,
    schema: dict[str, Any] | None = None,
    scopes: list[str] | None = None,
    requires_approval: bool = False,
    supports_staging: bool = False,
) -> Callable[[Callable[..., Any]], Tool]:
    """Decorator that turns a plain function into a `Tool`."""

    def _wrap(fn: Callable[..., Any]) -> Tool:
        return Tool(
            name=name,
            description=description,
            handler=fn,
            schema=schema or {'type': 'object', 'properties': {}},
            scopes=list(scopes or []),
            requires_approval=requires_approval,
            supports_staging=supports_staging,
        )

    return _wrap
