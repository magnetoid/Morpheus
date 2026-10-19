---
summary: Connects the store to an AI provider and turns it into product search, recommendations, daily insights and optional dynamic pricing.
---

## What it's for
This is where you connect the store to an AI provider — OpenAI, Anthropic, Gemini, OpenRouter, Grok, DeepSeek, Qwen Cloud and others — and switch on what it powers: smarter product search and "you might also like" suggestions on the storefront, the daily Insights list and the Pulse cards on the dashboard home, and, if you choose, automatic price changes. Linda, the assistant, uses this same connection to answer questions and work in the background.

## Set it up
Add an API key for at least one provider and choose it as the active provider; a blank key falls back to a server-level key where one is set. Then switch on only the features you want: meaning-based search, zero-shot product classification, dynamic pricing, or the autonomous operator, which lets scheduled runs act on their own timing instead of only when someone runs them by hand.

## Common tasks
- Add a key and choose the active provider in [](settings:ai_assistant).
- Turn on [](field:ai_assistant.enable_semantic_search) so search understands meaning, not only keywords.
- Turn on [](field:ai_assistant.enable_dynamic_pricing) to let prices adjust on their own.
- Read the day's suggestions and warnings on the dashboard home's Pulse cards, and dismiss the ones you've handled.
- Browse every open insight, not only the newest few, on the Insights page.
- Turn on [](field:ai_assistant.enable_autonomous_operator) so scheduled runs act without someone starting them.

## Good to know
Search and the "you might also like" suggestions on a product page fall back to plain catalog matching whenever this app is off or has no provider configured, so switching it off never breaks either. Pulse checks for low stock, abandoned carts, new returns, a drop in revenue, promotions ending soon, and poor reviews once a day and right after those events happen, and will not raise the same card twice while the first one is still unread. Synthetic testing is listed as a switch here but nothing behind it runs yet.
