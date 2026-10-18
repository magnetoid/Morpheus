---
summary: Lets customers join a free or paid membership plan and bills them automatically, with reminders when a payment fails.
---

## What it's for

This app runs recurring membership plans: a shopper signs up once and is billed automatically from then on. A plan can be free or charged through Stripe, and an active member can get a discount set on their plan. Staff manage plans and see subscriptions and invoices from the dashboard; shoppers manage their own membership from the storefront.

## Set it up

Create at least one plan from the [Subscriptions](page:subscriptions) page: a name, a price, how often it bills, and an optional member discount. A free plan works immediately. A paid plan needs Stripe set up in [Payments](app:payments) first — without it, a paid plan is shown as not currently available rather than letting someone sign up with no way to be charged.

## Common tasks

- Create a plan, change a plan's member discount, or deactivate it.
- See current subscriptions and recent invoices.
- Check membership performance on [Subscriptions](page:analytics) — revenue, cancellations, and how many trials convert.
- Ask Linda to list, pause, resume, or cancel a customer's subscription.

## Good to know

A member's discount is only applied once there is real evidence they paid for it — a free plan, a live Stripe subscription, or a paid invoice — never from a status alone, so it can never be granted for free by mistake. Failed payments get a short series of reminder emails, and members get a reminder a few days before they are billed again, both skipping anyone who has not agreed to marketing email. A recurring "box" style of subscription is modelled but is not yet something a shopper can actually start from the storefront.
