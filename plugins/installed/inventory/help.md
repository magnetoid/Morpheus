---
summary: Counts stock per warehouse, holds it for orders, moves it between warehouses and forecasts stockouts.
---

## What it's for

This app keeps track of how much stock each product has, per warehouse. It holds stock when a shopper checks out, removes it once the order is paid, and puts it back if the order is cancelled or a return is refunded. It can email a shopper once a sold-out product is back in stock, warns your team when something runs low or out, and forecasts which products are about to run out or are overstocked.

## Set it up

Nothing to switch on. Stock is counted only for a product with **Track inventory** ticked; a product without it can always be bought. Enter the units on hand in the Stock card on a product's page: the store gets "Main warehouse" the first time you do, and a product sold in one form gets a hidden default variant to hold its count.

## Common tasks

- Enter or correct units on hand per warehouse in the Stock card on a product's page, and tick **Backorders** to keep selling a variant when none is left.
- Add a warehouse, choose the default one, or switch one off on the [Warehouses](page:warehouses) page.
- Move free units from one warehouse to another on the same page; its list shows the latest stock changes and who made them.
- Set stock for many products at once with the `stock` and `warehouse_code` columns of the CSV import.
- Open the [Stockout forecast](page:stockout-forecast) report to see what is projected to run out soon, and what looks overstocked.
- Ask Linda for a product's stock, to set or change it, to move it between warehouses, or for a low-stock report; she asks before changing anything.

## Good to know

Orders take units from the switched-on warehouses, the default one first; a switched-off warehouse's stock is not sold, and units already held there for an order stay held. A warehouse with stock records cannot be deleted, because its history would go with it: move its stock out and switch it off. When a backordered variant sells beyond its stock, the order's timeline says how many units were ordered beyond what was on hand. Units held for open orders cannot be moved.
