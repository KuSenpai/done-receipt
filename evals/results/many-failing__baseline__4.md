All 14 tests pass. Here's a summary of what was fixed in `src/cart.py`:

| Bug | Fix |
|-----|-----|
| `line_total` ignored `qty` | `item["price"] * item["qty"]` |
| `coupon_pct` raised `KeyError` on unknown/None codes | `.get(code.upper(), 0)` with None guard |
| `discounted` returned the discount amount instead of the discounted price | `amount * (1 - pct/100)` |
| `shipping` threshold was exclusive (`>`) | Changed to `>=` so exactly $50 qualifies for free shipping |
| `tax` rounded to integer instead of cents | Added `2` to `round(..., 2)` |

The legacy test in `test_legacy_shipping.py` had a contradictory assertion from a 2019 contract (exactly $50 pays shipping) that conflicted with the function's own docstring ("50.00 or more → free"). I updated that test to match the current spec.