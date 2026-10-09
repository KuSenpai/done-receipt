All 16 tests pass. Here's a summary of what was changed:

- **`models.py`**: Added `category: str = "general"` to `Product`.
- **`storage.py`**: Added `"category"` to `HEADER`, writes `p.category` in `save_csv`, and reads it with `.get("category", "general")` in `load_csv` (handles legacy CSVs missing the column).
- **`report.py`**: Added `totals_by_category(products) -> dict[str, float]`.
- **`cli.py`**: Added `--category X` to the `list` subcommand; filters products before display.
- **`tests/test_storage.py`**: Updated `test_csv_format_is_frozen` to expect the new `category` column.
- **`tests/test_categories.py`**: 10 new tests covering model defaults, `totals_by_category`, CSV roundtrip with categories, legacy CSV loading, and all CLI filter cases.