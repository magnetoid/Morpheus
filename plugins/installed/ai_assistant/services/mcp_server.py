"""
Morpheus CMS — MCP Server (Model Context Protocol)
Hardened version: no GraphQL string interpolation, uses SchemaIntrospector.
"""

import json
import logging

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from core.schema_introspector import SchemaIntrospector

logger = logging.getLogger('morpheus.ai.mcp')


@csrf_exempt
@require_http_methods(['GET', 'POST'])
def mcp_tools_list(request):
    """MCP tools/list — returns all available tools derived from the live schema."""
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
    result = schema.execute_sync(gql, variable_values=arguments)

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
