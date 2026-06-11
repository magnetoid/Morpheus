"""
Morpheus CMS — Manifest views (OpenAI + Anthropic tool formats)
Refactored to use the canonical SchemaIntrospector — no more duplicated logic.
"""

from django.http import JsonResponse

from core.schema_introspector import SchemaIntrospector


def generate_openai_tools(request):
    """
    Law 0: Agentic First.
    Auto-generates OpenAI function calling definitions from the live GraphQL schema.
    """
    introspector = SchemaIntrospector()
    return JsonResponse({'tools': introspector.as_openai_tools()})


def generate_anthropic_tools(request):
    """
    Auto-generates Anthropic tool_use definitions from the live GraphQL schema.
    """
    introspector = SchemaIntrospector()
    return JsonResponse({'tools': introspector.as_anthropic_tools()})
