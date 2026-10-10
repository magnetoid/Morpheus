"""What another party needs to connect an agent to this store.

The API tokens page offers it per token: one block of text with everything
(store, endpoints, the header, how to reach Janus, what the token may do) and
ready configuration for the agents merchants use. The client formats follow each
project's own documentation (read 2026-10-10):

* Hermes Agent: ``~/.hermes/config.yaml``, ``mcp_servers.<name>`` with ``url``
  and ``headers`` (hermes-agent.nousresearch.com, user guide, MCP);
* OpenClaw: ``openclaw mcp set <name> '<json>'`` with ``url``,
  ``transport: streamable-http`` and ``headers`` (docs.openclaw.ai, CLI, MCP);
* Claude Code: ``claude mcp add --transport http <name> <url> --header ...``;
* Cursor and most other MCP clients: ``mcpServers.<name>`` with ``url`` and
  ``headers``.

The secret is in the text only when it was just created or replaced, the one
moment the page shows it; otherwise a placeholder stands in its place.
"""

from __future__ import annotations

import json

from django.utils.text import slugify

PLACEHOLDER = 'PASTE_YOUR_TOKEN_HERE'


def server_name(store_name: str) -> str:
    return (slugify(store_name or '') or 'morpheus-store')[:40]


def describe_scopes(scopes) -> str:
    if scopes is None:
        return 'everything (no limits set)'
    values = [str(s) for s in scopes]
    if not values:
        return 'nothing'
    if '*' in values:
        extra = sorted(v for v in values if v != '*')
        return 'everything' + (f' (+ {", ".join(extra)})' if extra else '')
    return ', '.join(sorted(values))


def connection_kit(*, base_url: str, store_name: str, entry: dict, secret: str = '') -> dict:
    """The connection details for ``entry``: ``text`` plus ``snippets``."""
    from plugins.installed.agent_mcp.janus_door import janus_granted

    token = secret or PLACEHOLDER
    base = (base_url or '').rstrip('/')
    mcp_url = f'{base}/mcp/admin/v1/'
    graphql_url = f'{base}/graphql/'
    name = server_name(store_name)
    label = str(entry.get('label') or 'API token')
    janus_mcp = janus_granted(entry, 'mcp')
    janus_graphql = janus_granted(entry, 'graphql')
    approved = sorted(str(t) for t in entry.get('approved_tools') or [])

    lines = [
        f'{store_name}: a Morpheus store at {base}',
        '',
        f'Token "{label}"',
        f'Authorization: Bearer {token}',
        'Send that header with every request.',
        '',
        'MCP server (Model Context Protocol, JSON-RPC 2.0 over HTTP):',
        f'  {mcp_url}',
        'GraphQL API:',
        f'  {graphql_url}',
        '',
    ]
    if janus_mcp or janus_graphql:
        lines.append("Janus, the store's own AI agent:")
        if janus_mcp:
            lines += [
                '  MCP tool janus.ask {"message": "..."} answers with',
                '  {status, reply, conversation, turn}. Pass "conversation" to continue a',
                '  conversation. If status is "running", call janus.reply {"turn": "..."}.',
            ]
        if janus_graphql:
            lines.append(
                '  GraphQL: mutation { askJanus(input: {message: "..."}) '
                '{ status reply conversation turn } }'
            )
        lines += ["  Janus works with this token's permissions, never more.", '']
    else:
        lines += [
            'Janus: not enabled for this token. The merchant can tick "Talk to Janus".',
            '',
        ]
    lines += [
        'What this token may do:',
        f'  MCP: {describe_scopes(entry.get("mcp_scopes"))}',
        f'  GraphQL: {describe_scopes(entry.get("graphql_scopes"))}',
        f'  Protected changes approved: {", ".join(approved) if approved else "none"}',
    ]

    header = f'Bearer {token}'
    openclaw = json.dumps(
        {'url': mcp_url, 'transport': 'streamable-http', 'headers': {'Authorization': header}},
        separators=(',', ':'),
    )
    cursor = json.dumps(
        {'mcpServers': {name: {'url': mcp_url, 'headers': {'Authorization': header}}}}, indent=2
    )
    snippets = [
        {
            'id': 'hermes',
            'label': 'Hermes Agent',
            'hint': 'Add to ~/.hermes/config.yaml, then restart Hermes.',
            'code': (
                'mcp_servers:\n'
                f'  {name}:\n'
                f'    url: "{mcp_url}"\n'
                '    headers:\n'
                f'      Authorization: "{header}"\n'
            ),
        },
        {
            'id': 'openclaw',
            'label': 'OpenClaw',
            'hint': 'Run once on the machine OpenClaw runs on.',
            'code': f"openclaw mcp set {name} '{openclaw}'",
        },
        {
            'id': 'claude-code',
            'label': 'Claude Code',
            'hint': 'Run once in a terminal.',
            'code': (
                f'claude mcp add --transport http {name} {mcp_url} '
                f'--header "Authorization: {header}"'
            ),
        },
        {
            'id': 'mcp-json',
            'label': 'Cursor and other MCP clients',
            'hint': 'Add to the client\'s mcp.json (or "MCP servers" settings).',
            'code': cursor,
        },
        {
            'id': 'curl',
            'label': 'Test with curl',
            'hint': 'Lists the tools this token can call.',
            'code': (
                f'curl -s {mcp_url} \\\n'
                f'  -H "Authorization: {header}" \\\n'
                '  -H "Content-Type: application/json" \\\n'
                '  -H "Accept: application/json, text/event-stream" \\\n'
                '  -d \'{"jsonrpc":"2.0","id":1,"method":"tools/list"}\''
            ),
        },
    ]
    if janus_graphql:
        query = {
            'query': (
                'mutation($m:String!){askJanus(input:{message:$m}){status reply conversation turn}}'
            ),
            'variables': {'m': 'What sold best this week?'},
        }
        snippets.append(
            {
                'id': 'graphql-janus',
                'label': 'Ask Janus over GraphQL',
                'hint': 'One question from a script.',
                'code': (
                    f'curl -s {graphql_url} \\\n'
                    f'  -H "Authorization: {header}" \\\n'
                    '  -H "Content-Type: application/json" \\\n'
                    f"  -d '{json.dumps(query, separators=(',', ':'))}'"
                ),
            }
        )
    return {
        'text': '\n'.join(lines),
        'snippets': snippets,
        'has_secret': bool(secret),
        'janus': janus_mcp or janus_graphql,
    }
