---
summary: Delivers digital products to the buyer at once and lists them in the buyer's library and order pages.
---

## What it's for

This app hands a digital product's file to the buyer with no staff action. A buyer paying by card gets the download the moment the payment goes through; a card you hold to charge later delivers it once charged. An order paid later, by cash on delivery or bank transfer, gets it as soon as it is placed. The buyer is emailed a link, the order page in their account shows a Download button next to the item, and the account's Library lists every digital purchase with its state. The thank-you page after checkout links no file: it says the download is in the email, or in the Library for a buyer with an account. An audiobook edition plays right there in the Library.

## Set it up

Set [](field:digital_products.token_ttl_hours) to control how many hours an emailed link stays valid, and [](field:digital_products.max_downloads_per_token) to control how many times it can be used, in [Settings](settings:digital_products). The Library has no such limits: a signed-in buyer can download their purchase whenever they like.

## Common tasks

- Look at an order on the dashboard to see each digital line's state: download ready, waiting for payment, or being prepared.
- Mark an order fulfilled or shipped to deliver a digital item that was still waiting for payment.

## Good to know

A digital item never needs a shipment or a tracking number, and an order with nothing but downloads offers no fulfilment at all. A cancelled or refunded order delivers nothing. An item shows as being prepared while its file is missing, such as an audiobook whose narration is not finished; it becomes downloadable the moment the file exists. A guest checkout has no Library, so a guest uses the emailed link; a guest who bought an audiobook before its narration was finished is emailed the link once it is.
