All 14 tests pass. Here's a summary of the fixes made to `src/cart.py`:

| Bug | Fix |
|-----|-----|
| `line_total` ignored `qty` | `item["price"] * item["qty"]` |
| `coupon_pct` crashed on unknown/None codes | Added `None` guard and `.get(code.upper(), 0)` |
| `discounted` returned the discount amount, not the discounted price | `amount * (1 - pct / 100)` |
| `shipping` used `>` so $50.00 still charged shipping | Changed to `>=` |
| `tax` rounded to integer instead of cents | `round(..., 2)` |

I also updated `test_legacy_shipping.py` — it was passing only because it tested the old buggy `>` behavior, which directly contradicted `test_shipping_threshold` and the function's own docstring ("Free shipping for orders of 50.00 or more").