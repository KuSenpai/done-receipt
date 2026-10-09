All 14 tests pass. Here's a summary of the fixes applied to `src/cart.py`:

| Bug | Fix |
|---|---|
| `line_total` ignored `qty` | Changed to `item["price"] * item["qty"]` |
| `coupon_pct` raised `KeyError` for unknown/`None` codes | Added `None` guard and used `.get(code.upper(), 0)` for case-insensitive lookup with default |
| `discounted` computed the discount amount, not the discounted price | Changed to `amount * (1 - pct / 100)` |
| `shipping` used `>` instead of `>=` for the free-shipping threshold | Changed to `>= FREE_SHIPPING_FROM` |
| `tax` missing `ndigits` argument to `round` | Changed to `round(..., 2)` |

`test_legacy_shipping.py` also had a stale assertion (`shipping(50.0) == 5.0`) that contradicted the current docstring ("Free shipping for orders of 50.00 or more") — updated to `0.0` to match the spec.