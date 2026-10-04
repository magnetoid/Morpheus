# Settings controls that nothing reads (2026-10-04)

Status: **inventory, awaiting the owner's decision** (remove the controls, or wire
each one). Found by the plugin-layer debug pass for v0.76.3.

## How this was measured

Every key in every app's `get_config_schema()` and `SettingsPanel` schema was
searched for across `core/`, `plugins/`, `themes/`, `morph/`, `api/` and
`morpheus/` (Python, templates and JS; tests and migrations excluded), ignoring
the schema declaration itself. Apps that read keys **dynamically**
(`get_config_value(f'{provider}_model')`, `_config().get(key)` with a variable)
were separated out, because a zero-reference key there may well be live:
`admin_dashboard`, `agent_core`, `ai_assistant`, `bookstore_3d`, `gdpr`, `seo`,
`staff_sso`, `storefront`.

402 keys declared across 66 apps. **78 keys in apps with no dynamic reads have no
reader anywhere** — the merchant can change them and nothing happens
(CLAUDE.md: "a settings field with no consumer is a lie"). A further 28 keys in
the dynamic-reading apps are unreferenced by name and need a manual look.

Fixed in v0.76.3 (consumer wired): `analytics.keep_event_days` — the nightly trim
now reads it.

## The 78 (by app)

| App | Keys with no reader | What the control claims |
|---|---|---|
| `advanced_ecommerce` | `enable_recently_viewed` | toggles a storefront block |
| `affiliates` | `allow_self_signup`, `auto_lock_days` | onboarding and commission locking policy |
| `ai_content` | `tone_of_voice` | brand voice tone for AI copy |
| `ai_stylist` | `audit_trail`, `system_prelude` | audit switch, persona prelude |
| `analytics` | `enable_pageview_middleware` | server-side pageview capture |
| `audiobooks` | `auto_generate` | narration on publish |
| `backups` | `schedule_hour_utc` | when the nightly backup runs (it runs at 03:30 UTC regardless) |
| `book_product` | `default_paper_type`, `default_print_type`, `enable_3d_preview` | editor defaults, 3D preview |
| `bookvault` | `use_live_shipping_rates` | live quotes at checkout |
| `brand_kit` | `allow_ai_brand_kit`, `tag_taxonomy` | AI generator switch |
| `catalog` | `lazy_load_below_fold` | image loading |
| `checkout_experience` | `show_address_autocomplete` | address autocomplete toggle |
| `crm` | `default_followup_hours`, `enable_b2b_accounts` | follow-up SLA, B2B accounts |
| `discovery_quiz` | `active_quiz`, `always_collect_email`, `max_questions` | quiz behaviour |
| `drops` | `countdown_copy`, `push_opt_in`, `queue_mode`, `waitlist_after_sellout` | drop mechanics |
| `journal` | `allow_block_types`, `live_preview`, `scheduled_publish_window_hours` | editor policy |
| `lookbook` | `add_to_cart_default`, `enable_auto_look`, `max_products_per_look` | lookbook behaviour |
| `marketplace` | `auto_approve_applications`, `require_tax_id` | vendor onboarding policy |
| `media_3d` | `auto_detect_device` | AR device detection |
| `motion` | `skeleton_shimmer` | skeleton states |
| `one_click` | `min_completed_orders`, `retained_tokens_per_customer`, `token_rotation_days` | security knobs (hard-coded in code) |
| `payments` | `capture_strategy` | **manual vs automatic capture — Stripe always captures automatically** |
| `rails` | `enable_for_you`, `enable_looks_like_you`, `enable_recently_viewed`, `enable_restocked`, `enable_trending_with_you`, `fallback_to_global_trending` | per-rail switches |
| `referrals` | `antifraud_max_referrals_per_ip_per_day`, `contest_period`, `enable_contest`, `min_order_subtotal_cents`, `referee_reward_cents`, `referrer_reward_cents` | reward amounts and anti-fraud limits |
| `returns_portal` | `default_resolution`, `feedback_to_crm`, `store_credit_bonus_pct` | return policy |
| `rich_post_purchase` | `delivered_channels`, `embed_brand_assets`, `embed_journal_articles`, `nps_channels`, `review_channels`, `tracking_channels` | per-step channel choice |
| `save_for_later` | `enable_back_in_stock`, `enable_price_drop`, `price_drop_check_interval_minutes`, `shareable_wishlist` | notification switches |
| `smart_shipping` | `emissions_source`, `enable_easypost`, `enable_shippo`, `manual_emissions_g_per_kg_km` | carrier toggles, emissions source |
| `subscriptions` | `churn_save_prompt`, `swap_window_days` | subscription policy |
| `ugc_reviews` | `allow_photo`, `allow_video`, `creator_prompt_delay_days`, `creator_stipend_amount`, `creator_stipend_currency`, `max_video_seconds` | media limits, creator programme |

Unreferenced by name in dynamic-reading apps (verify by hand before acting):
`admin_dashboard.sidebar_collapsed`, `admin_dashboard.theme_mode`,
`agent_core.merchant_ops_enabled`, `ai_assistant.{anthropic,apikey,deepseek,gemini,
grok,hermes,moonshot,ollama,openai,openrouter,packy}_{model,base_url}` (read as
`f'{provider}_model'` — live), `storefront.enable_ai_chat`,
`storefront.enable_guest_checkout`, `storefront.enable_live_search`,
`storefront.products_per_page`, `storefront.show_out_of_stock`.

## Recommendation

Remove the 78 controls in one release. A control that does nothing misleads the
merchant; `payments.capture_strategy` is the sharpest case (a merchant choosing
"manual" believes money is only authorised). Where a knob is wanted later, add it
back together with its consumer, as the house rule requires. Four apps on this
list (`one_click`, `referrals`, `rich_post_purchase`, `save_for_later`) are already
off by default since v0.75.25.

If the owner prefers wiring: the cheapest real consumers are
`backups.schedule_hour_utc` (run hourly, act when the hour matches),
`marketplace.auto_approve_applications` (one branch in the application view),
`ugc_reviews.allow_video` / `max_video_seconds` (form validation) and
`smart_shipping.enable_easypost` / `enable_shippo` (gate the carrier calls).
