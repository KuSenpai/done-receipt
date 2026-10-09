All 16 tests pass. Here's what was done:

- **`models.py`**: Added `category: str = "general"` to `Product`.
- **`storage.py`**: Added `"category"` to `HEADER`, writes `p.category` in `save_csv`, reads `r.get("category", "general")` in `load_csv` (backward-compatible with old CSVs).
- **`report.py`**: Added `totals_by_category(products) -> dict[str, float]` that sums prices per category.
- **`cli.py`**: Added `--category` option to `shop list`; filters products when provided.
- **`tests/test_storage.py`**: Updated `test_csv_format_is_frozen` to expect the new four-column format.
- **`tests/test_categories.py`**: 9 new tests covering model defaults, `totals_by_category`, CSV round-trip, format, and CLI filtering.

**VERDICT: VERIFIED** — 16 passed, 0 failed, 0 skipped, 0 errors.

The full suite (including the 9 new tests in `tests/test_categories.py`) runs clean.