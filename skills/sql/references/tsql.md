# T-SQL (SQL Server)

- **Identifiers:** `[col]` brackets, or `"col"` when `QUOTED_IDENTIFIER` is ON. Case-insensitive under the default collation.
- **Row limit:** `SELECT TOP (n) ...`; for paging use `ORDER BY ... OFFSET n ROWS FETCH NEXT m ROWS ONLY`. There is no `LIMIT`.
- **Window-function filter:** no `QUALIFY`. Wrap the query in a CTE or subquery and filter `WHERE rn = 1` on a `ROW_NUMBER() OVER (...)` column.
- **String aggregation:** `STRING_AGG(col, ',') WITHIN GROUP (ORDER BY ...)` (SQL Server 2017+).
- **Null:** `COALESCE` (ANSI, n-ary, returns the highest-precedence type) or `ISNULL(col, x)` (two-arg, returns the first argument's type). Prefer `COALESCE`.
- **Dates:** `GETDATE()` / `SYSDATETIME()`, `DATEADD(day, n, col)`, `DATEDIFF(day, start, end)` is **unit first, start before end**, `CAST` / `CONVERT` with style codes.
- **Upsert:** `MERGE` exists but has documented caveats (concurrency, triggers); many teams prefer explicit `INSERT` / `UPDATE` / `DELETE`. Use with care.
- **Procedures:** `CREATE OR ALTER PROCEDURE`. T-SQL is the dialect for ADF and meta-database stored-procedure logic.
- **JSON:** `OPENJSON`, `JSON_VALUE`, `JSON_QUERY`. There is no native `VARIANT` type.
- **Trap:** `ISNULL` vs `COALESCE` return-type difference can silently truncate; `DATEDIFF` can overflow `int` for large ranges in small units (use `DATEDIFF_BIG`).
