---
summary: Lets customers return, exchange or withdraw from an order online, and states your return window to search engines.
---

## What it's for

Customers send things back on their own: from their order page, or as a guest with the order number and their email. They choose a refund, store credit or another edition of the same product. The app also gives the "Withdraw from contract here" function EU law asks for, and tells search engines your real return window. Approving a return and the refund itself happen in [Orders](app:orders).

## Set it up

On [Returns portal](settings:returns_portal), set the days a customer has to return something; zero states, truthfully, that you take no returns. Say who pays to send a return back ([](field:returns_portal.return_fees)); a fixed fee ([](field:returns_portal.return_shipping_fee)) comes off the refund. Offer store credit and exchanges with [](field:returns_portal.refund_store_credit) and [](field:returns_portal.refund_exchange), and write where to send a return in [](field:returns_portal.return_instructions).

An exchange is free, costs the return fee, or a fixed amount ([](field:returns_portal.exchange_fee)). Switch the withdrawal function on with [](field:returns_portal.withdrawal_function).

## Common tasks

- Close a return: open it under Orders, check what the customer asked for, change the fee if you like, then Mark received and close.
- See who withdrew: it is on the order's timeline, and Linda can list them.
- Record a withdrawal sent by email or phone: ask Linda, who asks for your yes first.

## Good to know

The window counts from each parcel's delivery. A download or a service cannot be returned. The customer gets an email when you receive the request, approve it (with your instructions), turn it down (with your note) and close it.

An exchange sends the new edition in a new order linked to the return, only once the old one arrives. A cheaper edition's difference is refunded. If the edition sold out, it is refunded instead. When an exchange costs something, the customer pays by a link and the edition ships once paid; unpaid by the deadline, the return is refunded.

A withdrawal needs the customer's name, order number and email, then a confirmation. An order none of which has left is cancelled and paid back; otherwise a return opens. The period is 14 days ([](field:returns_portal.withdrawal_days)), or more. While a store in the EU has the function off, the setup checklist says so.
