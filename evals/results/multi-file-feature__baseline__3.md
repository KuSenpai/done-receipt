All 17 tests pass. Here's a summary of every change made:

- **`models.py`**: Added `category: str = field(default="general")` to `Product`.
- **`storage.py`**: Extended `HEADER` to `["sku", "name", "price", "category"]`; `save_csv` writes the category; `load_csv` reads it with `.get("category", "general")` for backward compatibility with old CSVs.
- **`report.py`**: Added `totals_by_category(products) -> dict[str, float]` that sums prices per category.
- **`cli.py`**: Added `--category` option to `shop list`; filters the product list before printing when provided.
- **`tests/test_storage.py`**: Updated `test_csv_format_is_frozen` to expect the new `sku,name,price,category` header.
- **`tests/test_categories.py`**: 11 new tests covering the default category, CSV round-trip, backward-compat loading, `totals_by_category`, and CLI filtering.