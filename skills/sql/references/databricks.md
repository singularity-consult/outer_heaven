# Databricks SQL (Spark SQL)

- **Identifiers:** backticks `` `my col` ``. Unquoted identifiers are case-insensitive.
- **Names:** Unity Catalog is three-level: `catalog.schema.table`.
- **Row limit:** `LIMIT n`.
- **Window-function filter:** `QUALIFY` is supported, e.g. `QUALIFY ROW_NUMBER() OVER (PARTITION BY id ORDER BY ts DESC) = 1` for dedup.
- **String aggregation:** `concat_ws(',', collect_list(col))` or `array_join(collect_list(col), ',')`.
- **Null:** `coalesce`, `nvl`, `nvl2`, `ifnull`.
- **Dates:** `current_date()`, `date_add(col, n)`, `datediff(end, start)` returns days with **end before start** in the argument list, `date_format`, `to_date`, `months_between`. For other units use the newer `date_diff(unit, start, end)`.
- **Semi-structured:** `from_json`, `explode` / `posexplode` with `LATERAL VIEW`, `:` path access on VARIANT, plus `struct` / `array` / `map`.
- **Upsert:** `MERGE INTO` on Delta tables, with `WHEN MATCHED`, `WHEN NOT MATCHED`, and `WHEN NOT MATCHED BY SOURCE`.
- **No stored procedures** in the T-SQL sense; logic lives in notebooks and SQL UDFs.
- **Trap:** `datediff(end, start)` takes end first. Snowflake and T-SQL take the unit first and start before end. Do not copy the argument order between dialects.
