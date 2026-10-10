# CJdropshipping + AliExpress dropshipping apps (2026-10-10)

Owner: "napravi i CJdropshipping app i AliExpress na Irving Survival — stavi u repo
ali ga enable samo na Irving Survival" (worldwide dropshipping for a store whose
catalogue is electronics-heavy: antennas, routers, solar, radios, tools, hygiene).

Both are **opt-in** apps (`MORPHEUS_EXTRA_APPS`), enabled only on Irving Survival,
built on the shared supplier package `plugins/dropshipping/` (with dsers and
zendrop): `eligible_orders`, `normalised_address`, `ship_with_tracking`, and the new
`importer.py` (draft product + variants + photos through the catalog app's own
services, sale price = cost × markup, supplier HTML through
`core.utils.html.sanitize_richtext` after script/style blocks are removed).

Why these two: CJ's API is open to any account (no partner review), ships worldwide
from CN/US/EU/GB warehouses, and covers the whole loop (catalogue, freight, order,
balance payment, tracking, signed webhooks). AliExpress' Open Platform DS API is the
widest catalogue, but needs an approved developer app and the merchant's OAuth
consent; DS orders are paid in the AliExpress account. DSers (CSV) and Zendrop (MCP)
stay for stores that already use them.

## CJ Open API 2.0 — the contract the app is built on

Source: developers.cjdropshipping.com (English API pages, read 2026-10-10). Base
`https://developers.cjdropshipping.com/api2.0/v1`; headers `CJ-Access-Token`,
`Content-Type: application/json`.

- **Success** = HTTP 200 **and** (`code == 200` or no `code`). Trust codes, never
  `message`. 1600001/1600002 = bad/missing token (fetch again once). 1600200 = rate,
  429/16900500 = out of daily points, 1603003 = order number already exists,
  1604000 = balance insufficient, 1605001 = logistic invalid.
- **Auth**: `POST /authentication/getAccessToken {"apiKey"}` → `data.openId`,
  `accessToken`, `refreshToken` (both 180 days; the same token for 24 h; the call is
  limited to 1/s). The key comes from My CJ → Authorization → API (install the API
  app, "Add API", type API Key). `openId` is the webhook signing secret.
- **Limits**: 1–6 requests/s by account level, 10/s per IP, 3 CJ users per IP; a
  daily points budget (50,000 + order conversion): `listV2` 50 points, detail /
  stock / freight 10, order calls free. 30 days without a transaction suspends API
  access.
- **Search**: `GET /product/listV2?keyWord=&page=&size=` → `data.content[].productList[]`
  (`id`, `nameEn`, `sku`, `bigImage`, `sellPrice` — may be a range "8.13-8.62",
  `warehouseInventoryNum`).
- **Detail**: `GET /product/query?pid=` → `pid`, `productNameEn`, `productImageSet[]`,
  `description` (HTML), `sellPrice`, `variants[]` (`vid`, `variantNameEn`, `variantKey`,
  `variantSku`, `variantImage`, `variantSellPrice` USD).
- **Freight**: `POST /logistic/freightCalculate {startCountryCode, endCountryCode, zip,
  products[{quantity, vid}]}` → `[{logisticName, logisticPrice, logisticAging,
  totalPostageFee}]`.
- **Order**: `POST /shopping/order/createOrderV2` — required `orderNumber`,
  `shippingCountryCode` + `shippingCountry`, `shippingProvince`, `shippingCity`,
  `shippingCustomerName`, `shippingAddress`, `logisticName`, `fromCountryCode`,
  `products[{vid, quantity, storeLineItemId}]`; `payType` 2 = pay from balance now,
  3 = create only. Response `orderId`, `orderStatus`, `actualPayment`,
  `interceptOrderReasons[]`.
- **Pay later**: `PATCH /shopping/order/confirmOrder {orderId}` then
  `POST /shopping/pay/payBalance {orderId}`.
- **Status**: `POST /shopping/order/getOrderDetailBatch {orderIds ≤100}` → `orderStatus`
  (CREATED, IN_CART, UNPAID, UNSHIPPED[PENDING|PROCESSING], SHIPPED, DELIVERED,
  CANCELLED), `trackNumber`, `trackingProvider`, `trackingUrl`.
- **Delete**: `DELETE /shopping/order/deleteOrder?orderId=` — only CREATED / IN_CART.
- **Webhooks**: `POST /webhook/set` with `product`, `stock`, `order`, `logistics` (all
  four required) as `{type: ENABLE|CANCEL, callbackUrls: [one public https URL]}`. CJ
  sends a test payload first and the registration fails unless the URL answers 200 in
  3 s. Header `sign` = Base64(HMAC-SHA256(key = str(openId), raw body)) — the docs'
  vector: openId `123`, body
  `{"messageId":"123111","messageType":"INSERT","params":"123","type":"PRODUCT"}` →
  `AHxoGFMoS/4mZfJ5vFes5//Pz2QibFQhh3GlrTtnWpk=`. Messages `{messageId, type,
  messageType, params}`: ORDER (`cjOrderId`, `orderNumber`, `orderStatus`,
  `trackNumber`…), LOGISTIC (`orderId`, `storeOrderNumbers[]`, `trackingNumber`,
  `trackingProvider`, `trackingUrl`, `trackingStatus` 0–14), STOCK (map vid →
  [{storageNum}]), VARIANT (`vid`, `variantSellPrice`). Retried ≤ 3 times; a topic
  below 80% success for two hours is closed and must be re-enabled. Stock/price
  messages only for products subscribed with `POST /webhook/product/subscribe`.

### What the app does with it (`plugins/installed/cjdropshipping/`)

- `CJLink` (product/variant → vid, cost, stock) and `CJOrder` (order → CJ order id,
  status, tracking).
- Import from the dashboard search → draft product, linked, subscribed to webhooks.
- `ORDER_PAID` queues the send; a beat sweep (`cjdropshipping.sync`, 20 min) sends
  what was missed and refreshes every open order. Sends are idempotent (row lock on
  `CJOrder`; 1603003 adopts CJ's existing order).
- The webhook view always answers 200 (an unsigned registration probe must pass) and
  acts only on a message whose signature verifies; `messageId` is applied once.
- Store cancellation deletes the CJ order while CJ allows it, else flags it.

## AliExpress Open Platform (IOP) DS API — the contract the app is built on

Source: openservice.aliexpress.com (API reference + the official Java/Python/PHP
SDKs, read 2026-10-10).

- **Access**: register as a "Drop Shipping" developer, create an app (AliExpress
  reviews it; AppKey + AppSecret), set its **callback URL** to
  `https://<store>/dashboard/aliexpress/oauth/callback/`. The merchant's AliExpress
  buyer account must have joined the Dropshipping Program (ds.aliexpress.com).
- **Gateway**: business methods `POST https://api-sg.aliexpress.com/sync` with
  `method=<dotted name>`; system (OAuth) methods
  `POST https://api-sg.aliexpress.com/rest/auth/token/create` and `…/refresh`.
  System parameters `app_key`, `timestamp` (epoch ms), `sign_method=sha256`,
  `sign`, and the merchant's `access_token` on business calls.
- **Signature**: uppercase hex HMAC-SHA256 (key = AppSecret) over every sent
  parameter except `sign`, empty values skipped, sorted by name in ASCII order,
  concatenated `key+value`; a system method puts its API path in front. Official
  vectors (in the tests): business, secret `helloworld`, params `access_token=test`,
  `aliexpress_category_id=200135143`, `app_key=123456`,
  `method=aliexpress.logistics.redefining.getonlinelogisticsinfo`,
  `sign_method=sha256`, `timestamp=1517820392000` →
  `F7F7926B67316C9D1E8E15F7E66940ED3059B1638C497D77973F30046EFB5BBB`; system,
  path `/auth/token/create`, `app_key=12345678`,
  `code=3_500102_JxZ05Ux3cnnSSUm6dCxYg6Q26`, same method/timestamp →
  `35607762342831B6A417A0DED84B79C05FEFBF116969C48AD6DC00279A9F4D81`.
- **OAuth**: `https://api-sg.aliexpress.com/oauth/authorize?response_type=code&force_auth=true&redirect_uri=…&client_id=<AppKey>&state=…`
  → the callback gets `code` (valid minutes) → `/auth/token/create {code}` →
  `access_token`, `refresh_token`, `expire_time`, `refresh_token_valid_time` (epoch
  ms), `user_nick`/`account`. A launched app's token lives 30 days and its refresh
  token 60; while the app is in testing, 1 and 2 days.
- **Responses**: wrapped in `<method_with_underscores>_response`; lists inside
  `{"<item_name>": [...]}`; errors as `{"error_response": {code, msg, sub_code,
  sub_msg}}`; business failures often HTTP 200 with flags in `result`.
- **Search**: `aliexpress.ds.text.search` (`keyWord`, `local=en_US`, `countryCode`,
  `currency`, `pageSize`, `pageIndex`) → `data.products[]` (`itemId`, `title`,
  `itemMainPic`, `targetSalePrice`, `targetOriginalPriceCurrency`, `orders`,
  `evaluateRate`).
- **Detail**: `aliexpress.ds.product.get` (`product_id`, `ship_to_country`,
  `target_currency`, `target_language`) → `ae_item_base_info_dto` (`subject`,
  `detail`), `ae_multimedia_info_dto.image_urls` (";"-separated),
  `ae_item_sku_info_dtos[]` (`sku_id`, `sku_attr`, `offer_sale_price`,
  `sku_available_stock`, `ae_sku_property_dtos[]`). Prices come in `target_currency`.
- **Freight**: `aliexpress.ds.freight.query {queryDeliveryReq: {quantity,
  shipToCountry, productId, selectedSkuId, language, locale, currency}}` →
  `result.delivery_options[]` (`code`, `company`, `shipping_fee_cent`,
  `free_shipping`, `min/max_delivery_days`). An order names the option's `code`.
- **Order**: `aliexpress.ds.order.create` with
  `param_place_order_request4_open_api_d_t_o = {out_order_id, logistics_address
  {address, address2, city, province, country, zip, contact_person, full_name,
  mobile_no}, product_items[{product_id, product_count, sku_attr,
  logistics_service_name}]}`. `out_order_id` is an idempotency key for 24 h. The
  United Kingdom is `UK`, not `GB`. Response `result.is_success`,
  `result.order_list` (one AliExpress order per seller), `error_code`/`error_msg`.
  Optional `ds_extend_request = {payment: {pay_currency: USD, try_to_pay: true}}`
  pays through PayPal, only for accounts AliExpress whitelisted
  (ds-api@aliexpress.com).
- **Payment**: otherwise the merchant pays each order in the AliExpress account
  before `pay_timeout_second` runs out, or AliExpress closes it.
- **Status**: `aliexpress.trade.ds.order.get {single_order_query: {order_id}}` →
  `order_status` (PLACE_ORDER_SUCCESS, WAIT_SELLER_SEND_GOODS,
  SELLER_PART_SEND_GOODS, WAIT_BUYER_ACCEPT_GOODS, FINISH, IN_CANCEL, …),
  `pay_timeout_second`.
- **Tracking**: `aliexpress.ds.order.tracking.get {ae_order_id, language}` →
  `data.tracking_detail_line_list[]` (`mail_no`, `carrier_name`).
- **No cancel method** and no webhooks the app relies on.

### What the app does with it (`plugins/installed/aliexpress/`)

- `AELink` (product/variant → product id, `sku_attr` for orders, `sku_id` for
  freight quotes, cost, stock) and `AEOrder` (order → the AliExpress order ids,
  payment deadline, tracking per AliExpress order).
- Connect: the page sends the merchant to AliExpress with a random `state` kept in
  the session; the callback refuses any other state, exchanges the code and keeps
  the tokens on the app's config row outside the settings schema (a settings save
  never touches them; a form never shows them). Every call refreshes the token when
  under two days are left, and the 30-minute sweep keeps it fresh.
- Import from the dashboard search through the shared importer → draft product,
  one variant per SKU, linked (a single-SKU product orders with `sku_attr` "").
- `ORDER_PAID` queues the placement; the sweep (`aliexpress.sync`, 30 min) places
  what was missed and reads every open order: the payment deadline from
  `pay_timeout_second`, paid once every AliExpress order is past payment, tracking
  per AliExpress order. The store order ships the platform way only when every
  AliExpress order of it has a number (numbers joined).
- Placement is idempotent: a row lock on `AEOrder`, and `out_order_id` = the store
  order number. A failure keeps its reason and can be tried again from the page.
- A store cancellation is flagged for a manual cancel in AliExpress (an unpaid one
  closes by itself after its deadline).
- Delivery: a fixed service code from settings, else the cheapest option offered.

## Enabling on a store

Deploy the code first, then add the apps to that store's
`MORPHEUS_EXTRA_APPS` (Coolify env) and redeploy it; the migrations run on boot.
Irving Survival: `plugins.installed.zendrop,plugins.installed.cjdropshipping,plugins.installed.aliexpress`.
The merchant then pastes the CJ API key (Settings → Shipping → CJdropshipping),
registers the CJ webhooks from the CJ page, and for AliExpress saves the AppKey and
AppSecret and presses Connect on the AliExpress page.
