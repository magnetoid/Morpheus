---
summary: Emails a delivery check, a review request and an NPS survey after each order, and suggests one product on the order confirmation page.
---

## What it's for
After an order arrives, this app can email the customer three times: a check that it arrived, a request to review what they bought, and a short survey asking how likely they are to recommend you (NPS). It also shows one extra product on the order confirmation page, with a line of your own wording above it.

## Set it up
Every email starts off. Switch each one on and set its timing on [Post-purchase](settings:post_purchase): the arrival check counts hours after delivery ([](field:post_purchase.delivered_followup_delay_hours)), the review request and the survey count days. Edit their wording under Emails, like any other email the store sends.

The suggestion needs nothing: it falls back to your newest active product that the customer did not just buy. To choose one, type its slug and your own line on the same page.

## Common tasks
- Switch an email on or off, or change when it goes out
- Check the [NPS](page:nps) report for your score, responses by product, and recent low scores
- See the visits and orders the emails bring in the Attribution report, under the source "post_purchase"

## Good to know
The review request and the survey are marketing. They go only to a customer who accepted marketing at checkout when your store asks for consent, and each carries a one-click unsubscribe; someone who unsubscribes still gets the arrival check, which is about their order. A cancelled or refunded order gets nothing, and neither does an exchange sent for a return.

An email more than three days past its time is skipped, not sent late, so switching one on never mails customers from old orders. The emails start counting from delivery, or from shipping when no delivery is recorded.

The survey page needs no sign-in, takes a score from 0 to 10 and an optional comment, and keeps one response per order. A review request links straight to each product's own review form. Opens are not counted: the links carry the email's name, so the Attribution report counts the visits and orders they bring.
