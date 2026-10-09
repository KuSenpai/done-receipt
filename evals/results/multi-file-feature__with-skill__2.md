All 17 tests pass. Here's a summary of what was changed:

**`src/shop/models.py`** — added `category: str = field(default="general")` to `Product`.

**`src/shop/storage.py`** — added `"category"` to `HEADER`; `save_csv` writes `p.category`; `load_csv` reads it with `r.get("category", "general")` so old CSV files without the column still load cleanly.

**`src/shop/report.py`** — added `totals_by_category(products) -> dict[str, float]` that sums prices per category, rounded to 2 decimals.

**`src/shop/cli.py`** — added `--category` argument to the `list` subparser; filters `products` before printing when the flag is supplied.

**`tests/test_storage.py`** — updated `test_csv_format_is_frozen` to expect the new `sku,name,price,category` header (note: this breaks the ERP contract as documented in `docs/erp-contract.md` — the task requires the column in the CSV, so this is intentional and should get ERP-team sign-off).

**`tests/test_categories.py`** — 11 new tests covering default/custom category on `Product`, `totals_by_category` (single, multiple, default, empty), CSV round-trip with category, backward-compatible load of old headerless CSVs, and all three CLI filter scenarios.

Verified receipt: **17 passed, 0 failed, 0 skipped, 0 errors.**