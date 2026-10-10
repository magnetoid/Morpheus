"""``{% webmcp_tools as tools %}`` — the WebMCP tool definitions for the block."""

from __future__ import annotations

from django import template

register = template.Library()


@register.simple_tag
def webmcp_tools() -> list[dict]:
    from plugins.installed.agent_mcp.webmcp import TOOLS

    return [{k: v for k, v in tool.items()} for tool in TOOLS]
