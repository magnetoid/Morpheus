"""Markets agent tools.

markets.list was migrated here from core/assistant/tools/ecommerce.py so the
Market query lives in the plugin that owns it. Tool name + scope unchanged —
Linda sources it by name from the agent registry.
"""

from __future__ import annotations

from morpheus.core import ToolResult, tool


@tool(
    name='markets.list',
    description=(
        'List configured Markets — region/code/currency/locale + active '
        'flag + per-market price adjustment. Use this to answer "where '
        'are we selling and at what currency?".'
    ),
    scopes=['system.read'],
    schema={'type': 'object', 'properties': {}},
)
def markets_list_tool() -> ToolResult:
    from plugins.installed.markets.models import Market

    rows = [
        {
            'code': m.code,
            'label': m.label,
            'currency': m.currency,
            'locale': m.default_locale,
            'countries': list(m.country_codes or []),
            'price_adjustment_pct': str(m.base_price_adjustment_pct or 0),
            'is_active': m.is_active,
            'is_default': m.is_default,
        }
        for m in Market.objects.all()
    ]
    return ToolResult(
        output={'markets': rows, 'count': len(rows)}, display=f'{len(rows)} market(s)'
    )
