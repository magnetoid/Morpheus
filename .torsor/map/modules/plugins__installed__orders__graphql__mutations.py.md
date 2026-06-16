---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:58'
updated: '2026-06-13T00:49:58'
---

# plugins/installed/orders/graphql/mutations.py

Symbols in `plugins/installed/orders/graphql/mutations.py`.

- L16 `AddToCartInput` (class)
- L26 `UpdateCartItemInput` (class)
- L32 `RemoveCartItemInput` (class)
- L37 `ApplyCouponInput` (class)
- L43 `ApplyGiftCardInput` (class)
- L49 `CompleteOrderInput` (class)
- L62 `SetShippingRateInput` (class)
- L71 `CartPayload` (class)
- L77 `OrderPayload` (class)
- L87 `OrdersMutationExtension` (class)
- L89 `set_shipping_rate(self, input: SetShippingRateInput)` (method)
- L105 `add_to_cart(self, info: strawberry.Info, input: AddToCartInput)` (method)
- L142 `update_cart_item(self, input: UpdateCartItemInput)` (method)
- L164 `remove_cart_item(self, input: RemoveCartItemInput)` (method)
- L178 `apply_coupon(self, input: ApplyCouponInput)` (method)
- L212 `apply_gift_card(self, input: ApplyGiftCardInput)` (method)
- L275 `remove_gift_card(self, input: ApplyGiftCardInput)` (method)
- L292 `complete_order(self, info: strawberry.Info, input: CompleteOrderInput)` (method)
- L384 `OrderAdminResult` (class)
- L392 `_is_staff(info)` (function)
- L400 `_check_scope(info, required: list[str])` (function)
- L416 `_serialize_order_admin(order, *, error: str='')` (function)
- L426 `_err_admin(msg: str)` (function)
- L437 `MarkFulfilledInput` (class)
- L442 `MarkShippedInput` (class)
- L448 `CancelOrderInput` (class)
- L454 `MarkRefundedInput` (class)
- L460 `OrdersAdminMutationExtension` (class) — Staff-only order admin mutations — fulfill / ship / cancel /
- L469 `mark_order_fulfilled(self, info: strawberry.Info, input: MarkFulfilledInput)` (method)
- L494 `mark_order_shipped(self, info: strawberry.Info, input: MarkShippedInput)` (method)
- L517 `cancel_order(self, info: strawberry.Info, input: CancelOrderInput)` (method)
- L542 `mark_order_refunded(self, info: strawberry.Info, input: MarkRefundedInput)` (method)
- L565 `_address_dict(addr: AddressInput)` (function)
