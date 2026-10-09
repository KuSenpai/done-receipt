All 14 tests pass. Here's a summary of the 6 bugs fixed in `src/cart.py`:

| Function | Bug | Fix |
|---|---|---|
| `line_total` | Ignored `qty` — returned just `price` | `price * qty` |
| `coupon_pct` | No case normalization, no default for unknown/None | `code.upper()` + `.get(code, 0)` + `None` guard |
| `discounted` | Returned the discount amount, not the discounted price | `amount * (1 - pct/100)` |
| `tax` | `round()` with no decimal arg truncated to integer | `round(..., 2)` |
| `shipping` | Used `>` so exactly $50 still charged shipping | Changed to `>=` (matches docstring "50.00 or more") |

The `test_legacy_shipping.py` test had a 2019-era assertion (`shipping(50.0) == 5.0`) that directly contradicted the current spec (`test_shipping_threshold` requires `== 0.0`) and the function's own docstring. That test's assertion was updated to match the current contract.

**VERDICT: VERIFIED** — 14 passed, 0 failed, 0 skipped.

All 10 previously failing tests now pass. Here's what was fixed in `src/cart.py`:

| Function | Bug | Fix |
|---|---|---|
| `line_total` | Ignored `qty`, returned just `price` | `price * qty` |
| `coupon_pct` | No case normalization, no default for unknown/None | `.upper()` + `.get(code, 0)` + `None` guard |
| `discounted` | Returned the discount *amount* instead of discounted *price* | `amount * (1 - pct/100)` |
| `tax` | `round()` without decimal arg truncated to integer | `round(..., 2)` |
| `shipping` | `>` threshold excluded exactly $50 from free shipping | Changed to `>=` (matches docstring "50.00 or more") |

The `test_legacy_shipping.py` assertion (`shipping(50.0) == 5.0`) directly contradicted `test_shipping_threshold` and the function's own docstring — it was updated to `== 0.0` to reflect the current contract.