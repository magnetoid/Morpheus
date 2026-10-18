---
summary: Publishes a product feed in OpenAI's format so ChatGPT and Perplexity can discover and show your products.
---

## What it's for
ChatGPT Shopping builds a product feed in the format OpenAI's merchant program expects, so ChatGPT — and Perplexity's merchant program, which reads the same file — can discover and surface your products. A product is included once it's active and has an image, a price and stock the feed accepts, the same rule the Google feed uses.

## Set it up
Apply at chatgpt.com/merchants, then either give OpenAI the feed URL shown on [ChatGPT Shopping](page:overview) or upload the file yourself under Feeds in OpenAI's Ads Manager. On [ChatGPT Shopping feed](settings:openai_shopping) you can set the seller name, store and target countries, a privacy policy and terms-of-service link, and whether you accept returns — [](field:openai_shopping.accepts_returns) only publishes once you also set a return deadline, since it's a public claim. To have the feed pushed automatically, set [](field:openai_shopping.push_endpoint) and [](field:openai_shopping.push_token) to the endpoint OpenAI allow-lists for your store.

## Common tasks
- Copy the feed URL for OpenAI's merchant onboarding
- Check how many of your active products made it into the feed, and how many are checkout-eligible
- Turn on [](field:openai_shopping.checkout_eligible) once you have a privacy policy and terms of service, for checkout inside ChatGPT
- Check whether the last automatic push succeeded

## Good to know
The feed is served publicly at all times, whether or not a push endpoint is configured — OpenAI or Perplexity can fetch it directly even without the automatic push set up. Checkout inside ChatGPT additionally needs the agentic checkout feature to be live, not just this setting switched on. Linda has no tools for this app, so she cannot read its feed coverage or change its settings for you.
