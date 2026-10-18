---
summary: Runs an action automatically when something happens in your store, such as an order being placed or a product going out of stock.
---

## What it's for

This app watches for things happening in your store — an order placed, paid, fulfilled or cancelled, a return requested or refunded, a product going low or out of stock, a new customer, an abandoned cart, an overstocked product, or a failed automatic task — and, when one happens, carries out one or more actions for you: notify staff, add a note to the order, tag the customer, send the event to a web address, or have Linda carry out a task.

## Common tasks

- Create a [workflow](page:index): pick the trigger event from a list, then set what must be true for it to fire and what it should do.
- Test a workflow against a sample event before switching it on, from its own test page.
- Watch a workflow's run history to see what fired, what didn't, and why.
- Switch a workflow off without deleting it.

## Good to know

Picking the trigger is a simple list, but the condition that decides whether it fires and the actions it takes are both typed in as a strict, code-like format, following an example shown above each box — there is no drag-and-drop builder yet. A workflow that calls on Linda runs her in the background and does not wait for her to finish or ask you anything.
