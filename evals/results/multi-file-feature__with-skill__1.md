All 16 tests pass (VERIFIED). Here's a summary of every change made:

**`src/shop/models.py`** — added `category: str = "general"` as a defaulted field on `Product`.

**`src/shop/storage.py`** — extended `HEADER` to `["sku", "name", "price", "category"]`; `save_csv` writes the category column; `load_csv` reads it (falls back to `"general"` for old files without the column).

**`src/shop/report.py`** — added `totals_by_category(products) -> dict` that sums prices per category key.

**`src/shop/cli.py`** — added `--category` argument to the `list` subcommand; when supplied, filters products before rendering.

**`tests/test_storage.py`** — updated `test_csv_format_is_frozen` expected string to include the new `category` column (the ERP format changed; this is the intentional sign-off point).

**`tests/test_categories.py`** — 10 new tests covering: default/explicit category on `Product`, CSV roundtrip with categories, `totals_by_category` (normal, empty, single), and `--category` CLI filtering (match, no match, no filter).