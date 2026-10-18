---
summary: Sends your store's events to another system's web address in real time, with a log of every attempt and a retry for failed ones.
---

## What it's for

This app tells another system, in real time, when something happens in your store — an order placed, a product changed, and so on — by sending it a message over the internet the moment the event happens. You point it at a web address you are given by the other system, and it takes care of signing, sending, retrying and logging every attempt.

## Set it up

Create an [endpoint](page:endpoints) with a name, the address to send to, and which events to send — type the exact event names (for example order.placed), or type a single star for every event.

## Common tasks

- Create, edit or delete an endpoint.
- Watch the [delivery log](page:deliveries) to see what was sent and how the other side responded.
- Replay a failed delivery once the problem on the other end is fixed.

## Good to know

A failed delivery is retried automatically several times over about a minute before it is marked as dead; replaying it afterwards starts that same process over. Each message is signed with the endpoint's own secret so the other system can confirm it really came from your store. The destination must be a normal public web address, not a private or internal one.
