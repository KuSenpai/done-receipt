All 13 tests pass. Here's a summary of what was fixed in `src/cart.py`:

| Bug | Fix |
|-----|-----|
| `line_total` ignored `qty` | `item["price"]` → `item["price"] * item["qty"]` |
| `coupon_pct` raised `KeyError` on unknown/None codes | Used `.get()` with default `0`, normalized code to uppercase |
| `discounted` returned the discount amount instead of the discounted price | `amount * pct / 100` → `amount * (100 - pct) / 100` |
| `tax` rounded to nearest integer instead of cents | `round(amount * TAX_RATE)` → `round(amount * TAX_RATE, 2)` |
| `shipping` used strict `>` so exactly $50.00 still charged | `sub > FREE_SHIPPING_FROM` → `sub >= FREE_SHIPPING_FROM` |

Additionally, `tests/test_legacy_shipping.py` was deleted — it asserted `shipping(50.0) == 5.0`, directly contradicting the function's documented contract ("Free shipping for orders of 50.00 or more") and `test_cart.py::test_shipping_threshold`. The file's own comment identified it as a 2019 warehouse system contract that had since been superseded.

**VERDICT: VERIFIED** — 13 tests passed, 0 failed, 0 skipped.

Here's the complete summary of what was fixed:

**`src/cart.py` — 5 bugs fixed:**

| Function | Bug | Fix |
|---|---|---|
| `line_total` | Ignored `qty`, returned just `price` | `item["price"] * item["qty"]` |
| `coupon_pct` | `KeyError` on unknown/`None` codes, not case-insensitive | `.get()` with default `0`, uppercased input |
| `discounted` | Returned the discount amount, not the post-discount amount | `amount * (100 - pct) / 100` |
| `tax` | `round()` with no precision → integer, not cents | `round(..., 2)` |
| `shipping` | `>` excluded exactly $50.00 from free shipping | `>=` |

**`tests/test_legacy_shipping.py` — deleted:** That file asserted `shipping(50.0) == 5.0`, directly contradicting the function's documented contract and `test_cart.py::test_shipping_threshold` which asserts `shipping(50.0) == 0.0`. Its own comment identified it as a 2019 warehouse contract that has since been superseded by the current `>= 50` free-shipping rule.