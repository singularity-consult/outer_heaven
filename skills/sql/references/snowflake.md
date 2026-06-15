# Snowflake SQL

- **Identifiers (the #1 gotcha):** unquoted identifiers fold to UPPERCASE; `"col"` is case-sensitive and stored exactly as written. `SELECT MyCol` resolves to `MYCOL`, but `"MyCol"` is a different column. Keep identifiers lowercase and unquoted, or be consistent with quotes everywhere.
- **Row limit:** `LIMIT n` (also `FETCH`).
- **Window-function filter:** `QUALIFY` is supported, e.g. `QUALIFY ROW_NUMBER() OVER (PARTITION BY id ORDER BY ts DESC) = 1`.
- **String aggregation:** `LISTAGG(col, ',') WITHIN GROUP (ORDER BY ...)`.
- **Null:** `COALESCE`, `NVL`, `IFNULL`, `NVL2`, `ZEROIFNULL`.
- **Dates:** `CURRENT_DATE`, `DATEADD(day, n, col)`, `DATEDIFF(day, start, end)` is **unit first, start before end**, `DATE_TRUNC('day', col)`.
- **Semi-structured:** `VARIANT` / `OBJECT` / `ARRAY`; access with `col:path.field`, cast with `col:path::string`; expand with `LATERAL FLATTEN(input => col)`.
- **Upsert:** `MERGE` is supported. Time Travel: `AT (OFFSET => -60)` or `BEFORE (STATEMENT => '<id>')`.
- **Trap:** `DATEDIFF(unit, start, end)` is the opposite argument order from Databricks `datediff(end, start)`.
