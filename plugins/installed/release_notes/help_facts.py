"""What the Help page says about an app that nobody writes down: where its
screens and settings are, what it adds to the shop, what Linda can do with it,
and its technical details. Read from the running code on every request, so it
cannot go stale, and asked of the app itself, so an app that is off still
answers.
"""

from __future__ import annotations

from plugins.installed.release_notes import help_markers

#: Storefront slots in a merchant's words. A slot an app fills that is missing
#: here shows its raw name, and tests/test_help_facts.py fails.
SLOT_WORDS: dict[str, str] = {
    'account_nav': "the shopper's account menu",
    'account_summary_extra': "the shopper's account overview",
    'auth_login_extra': 'the sign-in page',
    'cart_summary_extra': 'the cart summary',
    'checkout_extra': 'the checkout page',
    'footer_extra': 'the shop footer',
    'footer_legal': "the footer's legal links",
    'global_below_body': 'every shop page, at the end',
    'global_head': 'every shop page, out of sight in the page head',
    'home_above_grid': 'the home page, above the products',
    'home_after_rails': 'the home page, after the product rows',
    'home_below_grid': 'the home page, below the products',
    'journal': 'journal posts',
    'listing_below_description': "an experience's page, below its description",
    'order_receipt_extra': 'the order confirmation page',
    'pdp_above_long_description': 'the product page, above the long description',
    'pdp_below_form': 'the product page, under the buy form',
    'pdp_below_gallery': 'the product page, under the photos',
    'pdp_below_long_description': 'the product page, below the long description',
    'pdp_below_price': 'the product page, under the price',
    'shipping_rates': 'the shipping page, where the costs are listed',
}


def facts(name: str) -> dict | None:
    """Everything the Help page generates for one installed app, or None."""
    from core.assistant import gates
    from core.hooks import hook_registry
    from plugins.installed.admin_dashboard import navigation
    from plugins.registry import app_registry

    inst = app_registry.get(name)
    if inst is None:
        return None
    on = app_registry.is_active(name)
    places = [
        help_markers.page_link(p, name, on)
        for p in help_markers.pages_of(inst)
        if p.nav != 'hidden'
    ]
    where = help_markers.settings_link(inst, on)
    if where is not None and where not in places:
        places.append(where)
    cards = []
    for card in help_markers.ask_list(inst, 'contribute_dashboard_cards'):
        key = navigation.main_section_key(card.section)
        line = f'a card on {navigation.section_label(key)}' if key else ''
        if line and line not in cards:
            cards.append(line)
    blocks = help_markers.ask_list(inst, 'contribute_storefront_blocks')
    slots = list(dict.fromkeys(b.slot for b in blocks))
    tools = help_markers.ask_list(inst, 'contribute_agent_tools')
    # The tools Linda is ever offered: the edge's own rules (core/assistant/gates.py)
    # and inside her scope profile. The technical details still name every tool.
    linda_scopes = set(gates.LINDA_SCOPES)
    lindas = [
        t
        for t in tools
        if gates.linda_tool(t, developer=True)
        and set(getattr(t, 'scopes', None) or []) <= linda_scopes
    ]
    described = navigation.describe_app(inst)
    return {
        'name': name,
        'label': inst.label or name,
        'version': inst.version,
        'description': inst.description,
        'active': on,
        'area': described['area'],
        'area_label': described['area_label'],
        'places': places,
        'cards': cards,
        'shop': [SLOT_WORDS.get(s, s) for s in slots],
        'tools': [
            {
                'name': t.name,
                'description': t.description,
                'asks_first': gates.needs_consent(t),
                'developer': t.name in gates.DEVELOPER_TOOLS,
            }
            for t in lindas
        ],
        'tool_names': [t.name for t in tools],
        'requires': list(inst.requires or []),
        'required_by': sorted(
            p.name for p in app_registry.all_plugins() if name in (p.requires or [])
        ),
        'events': hook_registry.events_of(name),
        'slots': slots,
        'urls': app_registry.url_prefixes(name),
    }
