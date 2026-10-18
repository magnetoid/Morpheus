---
summary: Schedules a tracking, delivered, review-request and survey email per order; sending itself is not yet wired up.
---

## What it's for
This app is built to run four touchpoints after a purchase: a shipping notice once tracking is attached, a delivered check-in, a request to review what the customer bought, and a short survey asking how likely they are to recommend you (NPS). When an order is placed and later marked fulfilled, it records each of these against the order with the time it's due, on the schedule you set, so the same message is never scheduled twice.

## Set it up
Its settings page, [Post-purchase journey](settings:post_purchase), shows no fields to fill in today, so every step runs on its defaults: a delivered follow-up 24 hours after delivery, a review request after 14 days and a survey after 30 days, scored 0 to 10.

## Common tasks
- Check the [NPS](page:nps) report for your score, responses by product, and recent low scores
- Read a detractor's comment on the [NPS](page:nps) report to see why they scored low

## Good to know
Nothing in this install currently sends the tracking, delivered, review-request or survey emails it schedules — they are recorded against the order as due, but no message goes out on its own yet, so the survey link a customer would need never reaches them either. The survey page itself (when reached) needs no login, takes a score from 0 to 10 plus an optional comment, and keeps one response per order; a review request links straight to each book's own review form rather than a generic page.
