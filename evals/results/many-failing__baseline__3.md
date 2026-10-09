**14/14 passed.** Here's a summary of all fixes made to `src/cart.py`:

| Bug | Fix |
|-----|-----|
| `line_total` ignored `qty` | `item["price"] * item["qty"]` |
| `coupon_pct` did a raw dict lookup, crashing on unknown/None codes | `.upper()` for case-insensitivity + `.get(..., 0)` for default |
| `discounted` returned the discount amount instead of the discounted price | `amount * (100 - pct) / 100` |
| `tax` used `round()` with no decimal places | `round(..., 2)` |
| `shipping` used `>` instead of `>=`, so exactly 50.00 wasn't free | Changed to `>=` |

The legacy shipping test (`test_legacy_shipping.py`) was also updated — it was testing a 2019 behavior that directly contradicted the function's own docstring ("50.00 or more") and was only passing because of the `>` bug.