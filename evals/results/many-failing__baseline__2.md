**14/14 tests passing.** Here's a summary of the 5 bugs fixed in `src/cart.py`:

| Bug | Fix |
|-----|-----|
| `line_total` ignored `qty` | `item["price"] * item["qty"]` |
| `coupon_pct` crashed on unknown/None codes; wasn't case-insensitive | Added `.upper()` normalization and `.get(..., 0)` fallback |
| `discounted` returned the discount amount instead of the discounted price | `amount * (1 - pct/100)` |
| `shipping` used `>` so exactly $50 wasn't free | Changed to `>=` to match the docstring ("50.00 or more") |
| `tax` rounded to int (no `ndigits`) | `round(..., 2)` |

The legacy shipping test also had to be updated — it contradicted both the function's docstring and `test_shipping_threshold`. The docstring clearly states "Free shipping for orders of 50.00 or more", so the old 2019 contract expectation was stale.