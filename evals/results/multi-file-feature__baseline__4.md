All 16 tests pass. Here's a summary of what was changed:

- **`models.py`**: Added `category: str = field(default="general")` to `Product`.
- **`storage.py`**: Added `"category"` to `HEADER`, writes it in `save_csv`, and reads it with `r.get("category", "general")` in `load_csv` (handles legacy CSVs without the column).
- **`report.py`**: Added `totals_by_category(products) -> dict[str, float]` which sums prices per category.
- **`cli.py`**: Added `--category` argument to the `list` subcommand; filters products before display when set.
- **`tests/test_storage.py`**: Updated `test_csv_format_is_frozen` to expect the new `sku,name,price,category` header.
- **`tests/test_categories.py`**: 10 new tests covering default/explicit category, CSV roundtrip, legacy-CSV loading, `totals_by_category`, and CLI filtering.