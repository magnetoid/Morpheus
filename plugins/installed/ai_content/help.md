---
summary: Sets the store's brand voice for AI-written text, and marks product text an AI wrote on the product page.
---

## What it's for
This is where you set the store's brand voice — a name, an audience, a tone, and any specific writing rules — so every piece of AI-written text across the store sounds consistent instead of generic. Linda and every other AI writing tool in the store read this same voice before they write anything.

It also keeps track of product text an AI wrote, so shoppers and search engines can tell. EU law (Article 50 of the AI Act) asks for text a model generates to be marked in a form machines can read.

## Set it up
Fill in as much of the brand voice as you care about: a name AI-written copy should use, a line on who shops here, a few tone words, and any free-form rules such as words to avoid or how long sentences should be. Leaving a field blank just skips it.

Turn on [](field:ai_content.label_ai_text) if you also want a sentence under an AI-written description that a shopper reads.

## Common tasks
- Set the name AI-written copy should use for the store in [](field:ai_content.brand_name).
- Describe who shops here in [](field:ai_content.brand_audience).
- List a few tone words, such as "playful, direct, technical," in [](field:ai_content.brand_tone).
- Add specific rules — words to avoid, signature phrases, sentence length — in [](field:ai_content.brand_voice_guidelines).
- See which of a product's texts are marked in the "Written with AI" card on its page in [](section:products), and untick a box once a person has written that text.
- Ask Linda which texts of a product are marked as written with AI.

## Good to know
A product's description, short description, meta title and meta description are marked when Linda or an AI worker writes them, when you use Draft with AI or Rewrite on the product page and save, and when a bulk AI rewrite changes them. Text sent by another system through an access token is not marked, because nothing says a model wrote it. A marked description or short description is said in the product page's structured data and on the page itself. Only you can clear a mark; Linda can read the marks but not remove them. Translations are not marked yet.

Nothing in the brand voice is required. Leave every field blank and AI-written text uses its own default voice; fill any of them in and every AI generation in the store — product descriptions, email rewrites, SEO drafts, Linda's own replies — picks it up automatically.
