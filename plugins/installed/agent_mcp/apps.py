"""
agent_mcp — Model Context Protocol server for the Morpheus catalog.

Exposes a curated subset of the platform's read tools (and optionally
checkout helpers) over a JSON-RPC 2.0 endpoint compatible with the MCP
spec (https://modelcontextprotocol.io). External AI agents — Claude,
ChatGPT, Perplexity, Copilot — can list available tools, call them
with structured arguments, and stream results.

Why this matters: agentic-commerce traffic is exploding (AI-referred
shoppers convert ~42% better than non-AI). Standing up an MCP-shaped
endpoint means Morpheus stores are discoverable through any
MCP-compatible AI client without per-platform integrations.

Wire transport: HTTP POST with JSON-RPC 2.0 envelope. Streaming via
SSE is left for a follow-up; most read flows complete in <1s so the
synchronous shape is fine for v1.

Auth: API key issued per-store via PluginConfig. Storefront and
public agents pass it as `Authorization: Bearer <key>`. Without a
key, only the discovery / tool list is exposed.
"""
