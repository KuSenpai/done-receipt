All 15 tests pass. Here's a summary of what was changed:

| File | Change |
|---|---|
| `src/shop/models.py` | Added `category: str = "general"` to `Product` |
| `src/shop/storage.py` | Added `"category"` to `HEADER`; writes/reads it in save/load (loads `"general"` as default for old CSVs missing the column) |
| `src/shop/report.py` | Added `totals_by_category(products) -> dict[str, float]` |
| `src/shop/cli.py` | Added `--category` argument to `list`; filters products before printing |
| `tests/test_storage.py` | Updated `test_csv_format_is_frozen` to match the new `sku,name,price,category` format |
| `tests/test_categories.py` | New file with 9 tests covering all four new behaviors |