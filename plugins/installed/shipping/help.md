---
summary: Sets shipping zones and costs, including live carrier rates and carrier labels, and adds the right cost to every order.
---

## What it's for

This app defines which countries and regions you ship to and what shipping costs in each one. The cost it works out is added to the order total automatically at checkout. Once you connect Shippo or EasyPost, it can quote a live rate from the carrier and buy the label for a parcel from the order page.

## Set it up

Add at least one [shipping zone](page:zones) with the countries or regions it covers, then add a rate to it. A rate can be a flat price, a price that turns free once the cart reaches an amount, a table of tiers by weight or by order total, or pickup, where the customer collects the order (free, or the fee you enter). Every amount is in your store's currency. To quote live rates or buy labels, add the carrier's key and your origin address on the same page. A label is bought at the cheapest rate, the fastest, or the carrier and service you name there.

## Common tasks

- Add or edit a zone, its countries and its rates on [Shipping zones](page:zones); the rates table says what each one charges.
- Give a rate up to ten tiers. The first tier starts at 0, so every cart gets a price.
- Buy a label for a parcel from the Shipping labels panel on an order, or ship everything left on the order with one label in one step.
- Ask Linda to list your zones, set a rate's price, or buy a label. She asks for your yes before she changes a rate or spends money on a label.

## Good to know

A carrier key is never shown again once saved: leave the box empty to keep it, or tick the box under it to remove it. A label bought for a parcel adds its tracking number when the parcel had none, and emails it to the customer. A label that was paid for is always kept on the order, even if recording the parcel fails. Whether tax is charged on shipping is set in the [Tax](app:tax) app.

Your store's shipping page lists the active rates with what each one costs, its delivery time and its free-shipping threshold, taken from here. With no rate set up, the page says that checkout shows the delivery options and their cost for the shopper's address, so it never promises a price checkout won't charge.
