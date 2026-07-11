"""
Morpheus CMS — legacy MCP shim (Model Context Protocol).

Staff-gated. This is the OLD experimental MCP surface (`/api/mcp/tools/*`);
the real, per-audience MCP cluster lives in the `agent_mcp` plugin
(`/mcp/storefront|cart|checkout|admin/v1/` — whitelisted reads for the
anonymous clusters, Bearer auth for admin). This shim executes arbitrary
`query_*` / `mutate_*` GraphQL fields, so it must never be reachable
anonymously: it shipped with `@csrf_exempt` and NO auth, and it executes
the schema without a request context (so resolver-level permission checks
that read the user see nobody). Both endpoints now require an
authenticated STAFF session; token/agent clients belong on agent_mcp.
"""

import json
import logging

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from core.schema_introspector import SchemaIntrospector

logger = logging.getLogger('morpheus.ai.mcp')


def _staff_denied(request) -> JsonResponse | None:
    """401 unless the request carries an authenticated staff session."""
    user = getattr(request, 'user', None)
    if user is not None and user.is_authenticated and user.is_staff:
        return None
    return JsonResponse(
        {
            'content': [
                {
                    'type': 'text',
                    'text': 'Authentication required (staff session). '
                    'Agent/token clients should use the agent_mcp servers '
                    'under /mcp/…/v1/ instead of this legacy endpoint.',
                }
            ],
            'isError': True,
        },
        status=401,
    )


@csrf_exempt
@require_http_methods(['GET', 'POST'])
def mcp_tools_list(request):
    """MCP tools/list — returns all available tools derived from the live schema."""
    if (denied := _staff_denied(request)) is not None:
        return denied
    introspector = SchemaIntrospector()
    return JsonResponse({'tools': introspector.as_mcp_tools()})


@csrf_exempt
@require_http_methods(['POST'])
def mcp_tools_call(request):
    """
    MCP tools/call — executes a tool via native GraphQL execution.

    Security hardening: arguments are passed as GraphQL variables, never
    interpolated into the query string (prevents injection attacks).
    """
    if (denied := _staff_denied(request)) is not None:
        return denied
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse(
            {'content': [{'type': 'text', 'text': 'Invalid JSON'}], 'isError': True}, status=400
        )

    tool_name: str = data.get('name', '')
    arguments: dict = data.get('arguments', {})

    if tool_name.startswith('query_'):
        operation = 'query'
        field_name = tool_name[len('query_') :]
    elif tool_name.startswith('mutate_'):
        operation = 'mutation'
        field_name = tool_name[len('mutate_') :]
    else:
        return JsonResponse(
            {'content': [{'type': 'text', 'text': f'Unknown tool: {tool_name}'}], 'isError': True},
            status=400,
        )

    # Build variable declarations from the provided arguments
    if arguments:
        var_decls = ', '.join(f'${k}: String' for k in arguments)
        arg_refs = ', '.join(f'{k}: ${k}' for k in arguments)
        gql = f'{operation}({var_decls}) {{ {field_name}({arg_refs}) }}'
    else:
        gql = f'{operation} {{ {field_name} }}'

    from api.schema import get_schema

    schema = get_schema()
    # Pass the request as GraphQL context so resolver-level permission
    # checks see the (staff) caller instead of nobody.
    result = schema.execute_sync(gql, variable_values=arguments, context_value={'request': request})

    if result.errors:
        logger.warning(f'MCP tool call error: {tool_name} → {result.errors}')
        return JsonResponse(
            {
                'content': [{'type': 'text', 'text': f'Error: {result.errors[0].message}'}],
                'isError': True,
            }
        )

    return JsonResponse(
        {
            'content': [{'type': 'text', 'text': json.dumps(result.data)}],
            'isError': False,
        }
    )
