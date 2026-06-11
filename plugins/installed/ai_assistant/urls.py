from django.urls import path

from plugins.installed.ai_assistant.services.mcp_server import mcp_tools_call, mcp_tools_list
from plugins.installed.ai_assistant.views.manifest import (
    generate_anthropic_tools,
    generate_openai_tools,
)

app_name = 'ai_assistant'

urlpatterns = [
    path('agent-tools/openai.json', generate_openai_tools, name='openai_tools'),
    path('agent-tools/anthropic.json', generate_anthropic_tools, name='anthropic_tools'),
    # Model Context Protocol (MCP) Endpoints
    path('mcp/tools/list', mcp_tools_list, name='mcp_tools_list'),
    path('mcp/tools/call', mcp_tools_call, name='mcp_tools_call'),
]
