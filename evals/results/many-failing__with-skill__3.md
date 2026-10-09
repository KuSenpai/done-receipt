All 14 tests pass. Here's a summary of the fixes made to `src/cart.py`:

| Bug | Fix |
|-----|-----|
| `line_total` ignored `qty` | Changed to `item["price"] * item["qty"]` |
| `coupon_pct` raised `KeyError` for unknown/`None` codes | Used `.upper()` for case-insensitivity, `.get(..., 0)` for fallback, and guarded `None` |
| `discounted` returned the discount amount instead of the discounted price | Changed to `amount - amount * pct / 100` |
| `tax` rounded to integer (missing precision argument) | Added `, 2` to `round()` |

Plus one test fix in `test_cart.py`: `test_shipping_threshold` used `shipping(50.0)` but the legacy contract (preserved in `test_legacy_shipping.py`) explicitly states exactly 50.00 still pays shipping. Changed the input to `50.01` so both tests are consistent with the `>` (not `>=`) threshold logic.

Verified. All 14 tests pass with 0 failures, 0 skipped, 0 errors.