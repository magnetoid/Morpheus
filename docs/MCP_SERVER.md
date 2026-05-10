# Morpheus MCP server

Every Morpheus install ships a [Model Context Protocol](https://modelcontextprotocol.io)
server at `/mcp/v1/`. External AI clients (Claude Desktop, Cursor,
Continue, custom agents) can list and call a curated subset of the
catalog read tools without per-vendor integrations.

## Endpoints

```
POST /mcp/v1/                JSON-RPC 2.0 (initialize | tools/list |
                             tools/call | resources/list | resources/read | ping)
GET  /mcp/v1/health/         Liveness probe
GET  /mcp/v1/manifest.json   ChatGPT-style plugin manifest
```

## Authentication

`Authorization: Bearer <api_key>` against the keys stored in
`PluginConfig['agent_mcp']['public_keys']`.

Without a key, only `initialize` and a redacted `tools/list` (names +
descriptions, no `inputSchema`) are exposed. With a key, every tool in
the curated whitelist is callable.

### Issuing a key

```bash
docker compose exec web python manage.py shell -c "
import secrets
from plugins.models import PluginConfig
key = 'mcp_' + secrets.token_urlsafe(32)
cfg, _ = PluginConfig.objects.update_or_create(plugin_name='agent_mcp')
data = cfg.config or {}
keys = data.get('public_keys') or []
if key not in keys:
    keys.append(key)
data['public_keys'] = keys
cfg.config = data
cfg.save()
print(key)
"
```

Store the resulting key somewhere safe — keys are not retrievable
once issued. To revoke, drop the value from the same list.

## Connecting from Claude Desktop

`~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or
`%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```jsonc
{
  "mcpServers": {
    "morpheus": {
      "transport": {
        "type": "http",
        "url": "https://YOUR-MORPHEUS-DOMAIN/mcp/v1/",
        "headers": {
          "Authorization": "Bearer mcp_YOUR_KEY"
        }
      }
    }
  }
}
```

Restart Claude. The server will appear under Tools as `morpheus-mcp`
with all 12 tools listed.

## Connecting from Cursor / Continue / custom

Any client that speaks JSON-RPC 2.0 over HTTP works. Minimal example:

```bash
curl -s -X POST https://YOUR-MORPHEUS-DOMAIN/mcp/v1/ \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer mcp_YOUR_KEY' \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "products.search",
      "arguments": {"query": "Austen", "limit": 5}
    }
  }'
```

## Tool whitelist

The server exposes 13 read-only tools (no writes, no admin). Updated
in `plugins/installed/agent_mcp/views.py:_PUBLIC_TOOL_NAMES`:

| Tool | Purpose |
|---|---|
| `products.search` | Search catalog by query / category / status |
| `products.get` | Single product detail by slug or id |
| `orders.search` | Order listing with filters |
| `orders.get` | Single order detail by number |
| `customers.search` | Customer search by email / name |
| `customers.get` | Single customer profile |
| `analytics.summary` | Revenue + orders summary for a date range |
| `analytics.top_products` | Best-selling products |
| `cms.pages` | Published CMS pages |
| `db.list_models` | Schema introspection — model names |
| `db.describe_model` | Field-level schema for one model |
| `db.count_rows` | Count rows in a model |
| `memory.recall` | Linda's stored merchant preferences (read-only here) |

Admin tools (`fs.*`, `logs.*`, `plugins.*`, `settings.*`) and write
tools are **never** exposed here. The MCP server is read-only by
design — agents drive shoppers, not operations.

## Resources

Three discoverable resource URIs (`resources/list` returns these):

- `morpheus://catalog/featured` — featured products
- `morpheus://catalog/recent` — newest 20 products
- `morpheus://analytics/today` — today's revenue + order count
