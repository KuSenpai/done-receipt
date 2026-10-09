All 15 tests pass. Here's a summary of every change made:

| File | Change |
|---|---|
| `src/shop/models.py` | Added `category: str = field(default="general")` to `Product` |
| `src/shop/storage.py` | Extended `HEADER` with `"category"`; `save_csv` writes it; `load_csv` reads it with `r.get("category", "general")` so legacy CSVs without the column still load correctly |
| `src/shop/report.py` | Added `totals_by_category(products) -> dict` that sums prices per category |
| `src/shop/cli.py` | Added `--category` argument to `list`; filters products before printing when supplied |
| `tests/test_storage.py` | Updated `test_csv_format_is_frozen` expected string to include the new `category` column |
| `tests/test_categories.py` | New file — 9 tests covering the default category, CSV round-trip with/without category, `totals_by_category`, and the CLI filter |