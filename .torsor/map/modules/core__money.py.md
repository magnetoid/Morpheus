---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-10T20:08:49'
updated: '2026-06-10T20:08:49'
---

# core/money.py

Symbols in `core/money.py`.

- L43 `CurrencyMismatch` (class) — Raised when arithmetic mixes two different currencies.
- L47 `_decimal_of(value: MoneyLike)` (function) — Pull a ``Decimal`` out of a Money / Decimal / int / float / str.
- L56 `_currency_of(value: MoneyLike, default: str='USD')` (function) — Pull a 3-letter ISO currency string out of a Money — or return
- L64 `quantize(value: MoneyLike, *, currency: str | None=None)` (function) — Quantize to 2 decimal places (HALF_UP), wrap as Money.
- L77 `money(amount: MoneyLike, currency: str='USD')` (function) — Construct a Money, quantized. Accepts any numeric input.
- L86 `same_currency(a: Money, b: Money)` (function) — True iff two Money values share a currency. Cheap str compare.
- L91 `assert_same_currency(a: Money, b: Money)` (function) — Raise ``CurrencyMismatch`` if the two Money values disagree.
- L99 `add(a: Money, b: Money)` (function) — ``a + b`` — currency-checked, quantized.
- L105 `sub(a: Money, b: Money)` (function) — ``a - b`` — currency-checked, quantized. Negative results allowed.
- L111 `mul(value: Money, factor: MoneyLike)` (function) — Multiply a Money by a Decimal-like factor. Quantized result.
- L121 `apply_pct(value: Money, percent: MoneyLike)` (function) — Apply a percentage (e.g. ``Decimal('5')`` for 5%) to a Money.
- L133 `is_positive(value: Money)` (function)
- L137 `is_zero(value: Money)` (function)
- L141 `zero(currency: str='USD')` (function) — ``Money(0, currency)`` — handy when initialising sums.
- L146 `cap(value: Money, ceiling: Money)` (function) — Clamp ``value`` to at most ``ceiling``. Currencies must match.
- L154 `floor_at_zero(value: Money)` (function) — Clamp ``value`` to zero — never go negative.
