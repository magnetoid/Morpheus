---
summary: Suggests one product on the order confirmation page and schedules four follow-up emails per order, which are not sent yet.
---

## What it's for
After an order is placed, this app shows one extra product on the confirmation page, with a line of your own wording above it, as a simple "you might also like" suggestion.

It is also built to run four touchpoints after a purchase: a shipping notice once tracking is attached, a delivered check-in, a request to review what the customer bought, and a short survey asking how likely they are to recommend you (NPS). When an order is placed and later marked fulfilled, it records each of these against the order with the time it's due, so the same message is never scheduled twice.

## Set it up
The suggestion needs nothing: it falls back to your newest active product that the customer did not just buy. To choose a specific product instead, type its slug and your own line of copy on [Post-purchase](settings:post_purchase).

The four touchpoints run on fixed timing: a delivered follow-up 24 hours after delivery, a review request after 14 days and a survey after 30 days, scored 0 to 10.

## Common tasks
- Choose the product suggested on the confirmation page, and the line above it
- Check the [NPS](page:nps) report for your score, responses by product, and recent low scores
- Read a detractor's comment on the [NPS](page:nps) report to see why they scored low

## Good to know
The suggestion only links to the product's page — it adds nothing to the order the customer just placed, and buying it is an ordinary new purchase. If the slug you typed no longer matches a real, active product, the suggestion quietly falls back to your newest one instead.

Nothing in this install currently sends the tracking, delivered, review-request or survey emails it schedules — they are recorded against the order as due, but no message goes out on its own yet, so the survey link a customer would need never reaches them either. The survey page itself (when reached) needs no login, takes a score from 0 to 10 plus an optional comment, and keeps one response per order; a review request links straight to each book's own review form rather than a generic page.
