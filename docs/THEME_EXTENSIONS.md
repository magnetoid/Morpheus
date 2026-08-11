# Theme extensions — the storefront slot contract

> Plugins inject content into the storefront *without touching the theme*. The theme owns the layout; plugins own the content of their slots. Both can evolve independently.

This is the Shopify "theme app extensions" pattern adapted to Morpheus. The primitive existed in core since v0.1 (`StorefrontBlock` + `{% storefront_blocks "slot_name" %}`); this document is the canonical slot catalogue and the contract a theme commits to.

## Why slots, not template edits

Without slots, every plugin that wants to show something on the storefront has to:

1. Find the merchant's active theme
2. Edit a template in `themes/library/<theme>/templates/`
3. Hope the merchant didn't customize that template
4. Conflict with every other plugin that wants the same spot

With slots:

1. The theme declares N named insertion points
2. Plugins contribute content via `contribute_storefront_blocks()`
3. The merchant toggles individual blocks on/off in `/dashboard/plugins/<plugin>/`
4. Theme + plugins evolve independently

## How a theme declares slots

In any storefront template:

```django
{% load storefront_blocks %}

<section class="pdp">
  ...
  <h1>{{ product.name }}</h1>

  {# Standard slot — every plugin that wants to inject "below the title"
     gets rendered here, in order of contribution priority. #}
  {% storefront_blocks "pdp_below_title" %}

  ...
</section>
```

That's the whole contract. The theme owns the slot name. The plugin matches it.

## How a plugin contributes a block

In any `app.py`:

```python
from morpheus import Plugin, StorefrontBlock

class TrustpilotImportPlugin(Plugin):
    name = 'trustpilot-import'
    label = 'Trustpilot Import'

    def contribute_storefront_blocks(self):
        return [StorefrontBlock(
            slot='pdp_below_title',
            template='trustpilot_import/_pdp_stars.html',
            priority=50,
        )]
```

The block template receives the full storefront page context — `product`, `request`, `cart`, etc. — and renders into the slot.

## Standard slot names — the canonical catalogue

Theme authors **MUST** include every slot in this catalogue (or it's not a Morpheus-compatible theme). Plugin authors **MAY** target any of them. The slot name is the contract — case-sensitive, never renamed.

### Global slots (rendered on every page)

| Slot | Position | Typical use |
|---|---|---|
| `every_page_above_header` | Above `<header>` | Announcement bar, GDPR banner, free-shipping strip |
| `every_page_below_header` | Just below the header | Marquee, secondary nav, breadcrumb extension |
| `every_page_above_footer` | Just above `<footer>` | Newsletter signup, "you might also like" recommender |
| `every_page_below_footer` | Inside `<footer>`, last child | Tracking pixels, chat widget root |
| `head_extra` | End of `<head>` | Custom `<meta>`, JSON-LD, third-party CSS |

### PDP slots

| Slot | Position | Typical use |
|---|---|---|
| `pdp_above_title` | Above the product name | Limited-edition pill, "Editor's pick" badge |
| `pdp_below_title` | Below product name, above price | Star ratings, vendor link, sustainability badges |
| `pdp_below_price` | Below price, above add-to-cart | Klarna/Affirm widget, free-shipping note |
| `pdp_below_form` | Below the add-to-cart form | Trust badges, "Why choose us" |
| `pdp_above_long_description` | Above the long description | Product video, "On the cover" caption |
| `pdp_below_long_description` | Below the long description | Reader Q&A, related editorial |
| `pdp_after_reviews` | After the reviews section | Cross-sell, "Also bought together" |

### PLP / category slots

| Slot | Position | Typical use |
|---|---|---|
| `plp_above_grid` | Above the product grid | Category banner, filter hints |
| `plp_below_grid` | Below the product grid, above pagination | "We also recommend" recommender |
| `category_hero` | Inside category page hero | Editorial intro, video |

### Cart + checkout slots

| Slot | Position | Typical use |
|---|---|---|
| `cart_above_items` | Above the line items | Promo-code redemption, gift-message picker |
| `cart_below_items` | Below the line items, above the total | Free-shipping progress bar, upsell |
| `cart_below_total` | Below the total, above the checkout button | Trust badges, payment-icon strip |
| `checkout_above_address` | Top of the address step | Express-checkout buttons (Apple Pay, Shop Pay) |
| `checkout_above_payment` | Top of the payment step | Saved-card chooser, BNPL banner |
| `order_confirmation_below_total` | Below order total on the thank-you page | Post-purchase upsell, social share |

### Account slots

| Slot | Position | Typical use |
|---|---|---|
| `account_sidebar_extra` | Below the account sidebar nav | Custom account links (loyalty, wishlist, …) |
| `account_dashboard_above_orders` | Above the orders list on /account/ | Loyalty status, store-credit balance |

## Block priority + ordering

Multiple plugins can target the same slot. The runtime renders them in **ascending priority** — lower numbers first. Conventions:

- `priority=10` — "I should always be near the top" (announcement bar, trust badge)
- `priority=50` — default (most blocks should use this)
- `priority=90` — "render me last" (chat widget root, tracking pixels)

If two blocks have the same priority, render order is unspecified — write your plugin to not depend on a sibling's position.

## What this catalogue is NOT

- **NOT exhaustive of theme creativity.** A theme MAY add additional slots beyond this list for theme-specific patterns (a magazine-style theme might add `magazine_pull_quote_slot`). Plugins targeting non-standard slots only render when that theme is active.
- **NOT versioned per theme.** The catalogue is platform-wide. A theme either implements all standard slots or doesn't — partial compliance is not a thing.
- **NOT a replacement for direct template edits when the merchant wants them.** A merchant CAN copy a theme template into their `_overrides/` directory and customise. Slots are for *plugin authors*, not merchants — they avoid the "plugin asks merchant to add 12 lines of HTML" anti-pattern.

## Auditing existing plugins

The plugins listed below ALREADY contribute storefront blocks. New plugin authors should look at these for patterns:

- [`advanced_ecommerce`](../plugins/installed/advanced_ecommerce/app.py) — recently-viewed, free-shipping progress
- [`product_videos`](../plugins/installed/product_videos/app.py) — `pdp_above_long_description`
- [`product_gallery`](../plugins/installed/product_gallery/app.py) — `pdp_above_long_description` (the slider)
- [`reviews`](../plugins/installed/reviews/app.py) — `pdp_after_reviews` (the form), `pdp_below_title` (stars)
- [`wishlist`](../plugins/installed/wishlist/app.py) — `pdp_below_price` (heart icon)
- [`analytics`](../plugins/installed/analytics/app.py) — `every_page_below_footer` (page-view pixel)
- [`agent_core`](../plugins/installed/agent_core/app.py) — Linda concierge surface

Candidates that should be using slots but currently inject via template edits or direct CSS — *open follow-up*: `cart_abandonment` (recovery banner), `tracking` (GA4 pixel), `seo` (LD-JSON header injections move from `head_extra` would clean up base.html).

## Theme authoring checklist

1. ✅ Every standard slot from the catalogue above included
2. ✅ Slots placed in semantically correct positions (the "Typical use" column is the guideline)
3. ✅ Each `{% storefront_blocks "..." %}` immediately preceded by a comment naming the slot
4. ✅ No two slots stacked together — at least one block-level element between them
5. ✅ Theme template files only use `{% storefront_blocks %}` for the documented slot names, not arbitrary ones (or document the non-standard ones in the theme's README)

## Plugin authoring checklist

1. ✅ Block template lives in the plugin's own `templates/<plugin>/` directory
2. ✅ Block template never imports models directly — read from the request / page context
3. ✅ `priority` set explicitly (don't rely on the default)
4. ✅ Block renders gracefully when its data isn't available (degrade to nothing rather than crashing the page)
5. ✅ Each block toggleable via the plugin's settings panel — let the merchant turn off your block without disabling the whole plugin

## Why this is part of the CHARTER thesis

Per [`CHARTER.md` §4](../CHARTER.md#4-layered-architecture), themes (Layer 3) and plugins (Layer 4) must communicate through declared contracts. The slot catalogue IS that contract. Without it, plugins reach into theme templates → cross-layer coupling → broken plugin promise within a year.

This is the same primitive Shopify exposes as "theme app extensions" and Wordpress exposes as "hooks + filters" — adapted to Morpheus's Django + plugin-registry architecture.
