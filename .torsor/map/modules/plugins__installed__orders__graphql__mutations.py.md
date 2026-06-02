---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-02T18:07:52'
updated: '2026-06-02T18:07:52'
---

# plugins/installed/orders/graphql/mutations.py

Symbols in `plugins/installed/orders/graphql/mutations.py`.

- L18 `AddToCartInput` (class)
- L26 `UpdateCartItemInput` (class)
- L32 `RemoveCartItemInput` (class)
- L37 `ApplyCouponInput` (class)
- L43 `ApplyGiftCardInput` (class)
- L49 `CompleteOrderInput` (class)
- L62 `SetShippingRateInput` (class)
- L71 `CartPayload` (class)
- L77 `OrderPayload` (class)
- L87 `OrdersMutationExtension` (class)
- L90 `set_shipping_rate(self, input: SetShippingRateInput)` (method)
- L103 `add_to_cart(self, info: strawberry.Info, input: AddToCartInput)` (method)
- L130 `update_cart_item(self, input: UpdateCartItemInput)` (method)
- L150 `remove_cart_item(self, input: RemoveCartItemInput)` (method)
- L162 `apply_coupon(self, input: ApplyCouponInput)` (method)
- L184 `apply_gift_card(self, input: ApplyGiftCardInput)` (method)
- L217 `remove_gift_card(self, input: ApplyGiftCardInput)` (method)
- L229 `complete_order(self, info: strawberry.Info, input: CompleteOrderInput)` (method)
- L307 `OrderAdminResult` (class)
- L315 `_is_staff(info)` (function)
- L323 `_check_scope(info, required: list[str])` (function)
- L338 `_serialize_order_admin(order, *, error: str='')` (function)
- L346 `_err_admin(msg: str)` (function)
- L354 `MarkFulfilledInput` (class)
- L359 `MarkShippedInput` (class)
- L365 `CancelOrderInput` (class)
- L371 `MarkRefundedInput` (class)
- L377 `OrdersAdminMutationExtension` (class) — Staff-only order admin mutations — fulfill / ship / cancel /
- L386 `mark_order_fulfilled(self, info: strawberry.Info, input: MarkFulfilledInput)` (method)
- L407 `mark_order_shipped(self, info: strawberry.Info, input: MarkShippedInput)` (method)
- L426 `cancel_order(self, info: strawberry.Info, input: CancelOrderInput)` (method)
- L447 `mark_order_refunded(self, info: strawberry.Info, input: MarkRefundedInput)` (method)
- L466 `_address_dict(addr: AddressInput)` (function)
