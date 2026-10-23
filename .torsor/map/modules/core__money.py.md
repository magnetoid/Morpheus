---
type: map
status: derived
tags:
- map
links: []
created: '2026-10-23T04:51:49'
updated: '2026-10-23T04:51:49'
rules: []
---

# core/money.py

Symbols in `core/money.py`.

- L44 `CurrencyMismatch` (class) — Raised when arithmetic mixes two different currencies.
- L48 `_decimal_of(value: MoneyLike)` (function) — Pull a ``Decimal`` out of a Money / Decimal / int / float / str.
- L57 `_currency_of(value: MoneyLike, default: str='USD')` (function) — Pull a 3-letter ISO currency string out of a Money — or return
- L65 `quantize(value: MoneyLike, *, currency: str | None=None)` (function) — Quantize to 2 decimal places (HALF_UP), wrap as Money.
- L78 `money(amount: MoneyLike, currency: str='USD')` (function) — Construct a Money, quantized. Accepts any numeric input.
- L87 `money_str(value: MoneyLike | None)` (function) — Render a Money / Decimal / numeric amount as a plain decimal string.
- L102 `same_currency(a: Money, b: Money)` (function) — True iff two Money values share a currency. Cheap str compare.
- L107 `assert_same_currency(a: Money, b: Money)` (function) — Raise ``CurrencyMismatch`` if the two Money values disagree.
- L113 `add(a: Money, b: Money)` (function) — ``a + b`` — currency-checked, quantized.
- L119 `sub(a: Money, b: Money)` (function) — ``a - b`` — currency-checked, quantized. Negative results allowed.
- L125 `mul(value: Money, factor: MoneyLike)` (function) — Multiply a Money by a Decimal-like factor. Quantized result.
- L135 `apply_pct(value: Money, percent: MoneyLike)` (function) — Apply a percentage (e.g. ``Decimal('5')`` for 5%) to a Money.
- L147 `is_positive(value: Money)` (function)
- L151 `is_zero(value: Money)` (function)
- L155 `zero(currency: str='USD')` (function) — ``Money(0, currency)`` — handy when initialising sums.
- L160 `cap(value: Money, ceiling: Money)` (function) — Clamp ``value`` to at most ``ceiling``. Currencies must match.
- L168 `floor_at_zero(value: Money)` (function) — Clamp ``value`` to zero — never go negative.
