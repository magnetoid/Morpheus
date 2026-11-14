---
summary: Counts stock per warehouse, holds it for orders, moves it between warehouses and forecasts stockouts.
---

## What it's for

This app keeps track of how much stock each product has, per warehouse. It holds stock when a shopper checks out, removes it once the order is paid, and puts it back if the order is cancelled or a return is refunded. It emails a shopper when a sold-out product is back and warns your team when something runs low or out.

## Set it up

Nothing to switch on. Stock is counted only for a product with **Track inventory** ticked; a product without it can always be bought. The first count you enter gives the store a "Main warehouse", and a product sold in one form gets a hidden default variant to hold its count.

## Common tasks

- See stock across all your products on the [Stock](page:stock) page (Products → Inventory): search, and filter to what is low or out. To change a count, type it on [Stock](page:stock) or on the product's Stock card.
- Tick **Backorders** in a product's Stock card to keep selling a variant when none is left. While staff roles are enforced, changing stock takes its own permission: someone who may edit a product but not stock sees the numbers without boxes to change.
- Add a warehouse, choose the default one, or switch one off on the [Warehouses](page:warehouses) page.
- Move free units from one warehouse to another on the Warehouses page; its list shows the latest changes.
- The Low filter on [Stock](page:stock) lists free units at or below your low-stock threshold; Pulse and the home page show it too.
- Set many counts at once with the `stock` and `warehouse_code` columns of the CSV import.
- Open the [Forecast](page:stockout-forecast) tab beside Stock to see what is projected to run out soon, and what looks overstocked.
- Ask Linda to read, set or move stock, or for a low-stock report; she makes the same change the Stock page does, and asks before changing anything.

## Good to know

Orders take units from the switched-on warehouses, the default one first; a switched-off warehouse's stock is not sold, and units already held there for an order stay held. A warehouse with stock records cannot be deleted; switch it off instead. A backordered sale beyond stock is noted on the order's timeline. Units held for open orders cannot be moved.
