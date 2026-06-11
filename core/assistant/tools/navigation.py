"""Linda's dashboard navigation tool.

When a merchant asks something where the right answer is "open the X
page with these filters applied," Linda calls ``dashboard.navigate``
with the path + a one-line reason. The widget renders the result as
a click-through chip (NOT an auto-navigation — we don't yank the
merchant off the page they're on without consent).

This is the architectural complement to the floating widget on every
Ops Console page: chat → page navigation, page context already flows
back into chat (see runtime._page_context_system). The two surfaces
are now bridged in both directions.

Examples Linda should reach for:
  - "show me last week's pending orders"
      → dashboard.navigate('/dashboard/orders/?status=pending&date_from=...',
                           reason='Last week's pending orders')
  - "find the low-stock items"
      → dashboard.navigate('/dashboard/products/?inventory_lte=10',
                           reason='Products with ≤10 units left')
  - "open the SEO audit"
      → dashboard.navigate('/dashboard/seo/audit/',
                           reason='SEO audit dashboard')

The tool returns the URL it was asked to surface so Linda can also
mention it in her text reply. The widget reads the same fields from
the tool_call_finished event payload and renders the chip.
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

from core.assistant.tools.filesystem import ToolError, ToolResult, tool

_SAFE_PATH_RE = re.compile(r'^/dashboard/[a-zA-Z0-9/_\-\.]*(?:\?[a-zA-Z0-9=&%_\-\.\,/+]*)?$')


@tool(
    name='dashboard.navigate',
    description=(
        'Surface a dashboard deep-link for the merchant to click. Use this '
        'when the most useful answer is a page with filters applied — '
        'orders list filtered by status, products by inventory, the SEO '
        'audit, etc. The widget renders the URL as a chip; the merchant '
        'clicks to open. Do NOT use for storefront URLs or anything '
        'outside /dashboard/. Path MUST start with /dashboard/.'
    ),
    scopes=['system.read'],
    schema={
        'type': 'object',
        'properties': {
            'path': {
                'type': 'string',
                'description': (
                    'Relative path starting with /dashboard/, optionally '
                    'with query string. e.g. '
                    '"/dashboard/orders/?status=pending".'
                ),
            },
            'reason': {
                'type': 'string',
                'description': (
                    'One short line for the chip label, e.g. '
                    '"Last week\'s pending orders" or "Low-stock products".'
                ),
            },
        },
        'required': ['path', 'reason'],
    },
)
def dashboard_navigate_tool(*, path: str, reason: str, agent=None, context=None) -> ToolResult:
    """Return a navigation hint for the widget to render."""
    path = (path or '').strip()
    reason = (reason or '').strip()[:160]
    if not path:
        raise ToolError('path is required')
    # Defense in depth: only allow same-origin /dashboard/ paths so a
    # confused agent can't surface a phishing link.
    parsed = urlparse(path)
    if parsed.scheme or parsed.netloc:
        raise ToolError('Absolute URLs are not allowed; pass a path starting with /dashboard/.')
    if not path.startswith('/dashboard/'):
        raise ToolError('path must start with /dashboard/')
    if not _SAFE_PATH_RE.match(path):
        raise ToolError(
            'path contains unsupported characters; stick to letters, '
            'digits, hyphens, underscores, and a simple query string.'
        )
    return ToolResult(
        output={
            'path': path,
            'reason': reason or 'Open in dashboard',
            'kind': 'navigate',
        },
    )
