---
summary: Lets an outside AI shopping agent browse your catalogue and build an order; charging it is optional and off by default.
---

## What it's for

This app lets an outside AI shopping agent — the kind a customer might ask to find and buy something — discover your catalogue and put together an order directly against your store, instead of only linking the customer back to your site.

## Set it up

Switch the app on from Apps. To also accept a charge from an agent, turn on "Accept agent payments" under [Agentic Commerce Protocol](settings:agentic_checkout) — this needs Stripe set up in [Payments](app:payments) too. An outside agent is let in by a token carrying a specific permission; today, granting that permission from the token page does not work correctly, so no outside agent can actually create or complete an order through this app yet, even once everything above is switched on.

## Good to know

A completed agent order shows up in your normal orders list like any other order, so there is no separate screen to watch for them. A single product can be kept out of agent checkout entirely using a custom field on it, set from [Metafields](app:metafields). An agent's checkout session expires after an hour by default, which you can change.
