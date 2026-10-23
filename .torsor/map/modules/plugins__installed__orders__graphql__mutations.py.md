---
type: map
status: derived
tags:
- map
links: []
created: '2026-10-23T04:51:51'
updated: '2026-10-23T04:51:51'
rules: []
---

# plugins/installed/orders/graphql/mutations.py

Symbols in `plugins/installed/orders/graphql/mutations.py`.

- L18 `AddToCartInput` (class)
- L32 `UpdateCartItemInput` (class)
- L38 `RemoveCartItemInput` (class)
- L43 `ApplyCouponInput` (class)
- L49 `ApplyGiftCardInput` (class)
- L55 `CompleteOrderInput` (class)
- L68 `SetShippingRateInput` (class)
- L77 `CartPayload` (class)
- L83 `OrderPayload` (class)
- L95 `OrdersMutationExtension` (class)
- L97 `set_shipping_rate(self, info: strawberry.Info, input: SetShippingRateInput)` (method)
- L108 `add_to_cart(self, info: strawberry.Info, input: AddToCartInput)` (method)
- L151 `update_cart_item(self, info: strawberry.Info, input: UpdateCartItemInput)` (method)
- L168 `remove_cart_item(self, info: strawberry.Info, input: RemoveCartItemInput)` (method)
- L177 `apply_coupon(self, info: strawberry.Info, input: ApplyCouponInput)` (method)
- L204 `remove_coupon(self, info: strawberry.Info, input: ApplyCouponInput)` (method)
- L216 `apply_gift_card(self, info: strawberry.Info, input: ApplyGiftCardInput)` (method)
- L274 `remove_gift_card(self, info: strawberry.Info, input: ApplyGiftCardInput)` (method)
- L286 `complete_order(self, info: strawberry.Info, input: CompleteOrderInput)` (method)
- L395 `OrderAdminResult` (class)
- L403 `_serialize_order_admin(order, *, error: str='')` (function)
- L413 `_err_admin(msg: str)` (function)
- L424 `MarkFulfilledInput` (class)
- L429 `MarkShippedInput` (class)
- L435 `CancelOrderInput` (class)
- L441 `MarkRefundedInput` (class)
- L447 `OrdersAdminMutationExtension` (class) — Staff-only order admin mutations — fulfill / ship / cancel /
- L456 `mark_order_fulfilled(self, info: strawberry.Info, input: MarkFulfilledInput)` (method)
- L481 `mark_order_shipped(self, info: strawberry.Info, input: MarkShippedInput)` (method)
- L504 `cancel_order(self, info: strawberry.Info, input: CancelOrderInput)` (method)
- L529 `mark_order_refunded(self, info: strawberry.Info, input: MarkRefundedInput)` (method)
- L553 `_address_dict(addr: AddressInput)` (function)
