All 15 tests pass. Here's a summary of every change made:

| File | Change |
|---|---|
| `src/shop/models.py` | Added `category: str = "general"` field to `Product` |
| `src/shop/storage.py` | Added `"category"` to `HEADER`; writes `p.category` in `save_csv`; reads it with `.get("category", "general")` fallback in `load_csv` |
| `src/shop/report.py` | Added `totals_by_category(products) -> dict[str, float]` |
| `src/shop/cli.py` | Added `--category` argument; filters product list before display when provided |
| `tests/test_storage.py` | Updated `test_csv_format_is_frozen` expected string to include the new `category` column |
| `tests/test_categories.py` | New file — 9 tests covering default category, explicit category, `totals_by_category`, CSV round-trip, backward-compatible CSV load (no category column), and both `--category` filter variants |

**VERDICT: VERIFIED** — 15 passed, 0 failed, 0 skipped, 0 errors.

The full suite is green. All four changes (model field, CSV column, `totals_by_category`, `--category` CLI filter) are implemented and covered by the new `tests/test_categories.py`.