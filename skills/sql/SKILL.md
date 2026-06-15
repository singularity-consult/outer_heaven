---
name: sql
description: SQL conventions and dialect guidance for Benny's three dialects: Databricks SQL (Spark), Snowflake SQL, and T-SQL (SQL Server). Use this whenever you read or write SQL. Shared style lives here; dialect-specific syntax and gotchas live in references/{databricks,snowflake,tsql}.md, loaded on demand. Writing one dialect's syntax in another is the main failure this prevents.
---

# sql

Benny works across three SQL dialects. Their syntax diverges in ways that cause silent or hard errors if you write one dialect's syntax in another. This skill holds the shared style; the dialect-specific syntax and traps live in the reference files, which you read once you know which dialect you are in.

## Which dialect, and where its detail lives

- **Databricks SQL (Spark SQL)**: Lakehouse, notebook, and Unity Catalog work. See `references/databricks.md`.
- **Snowflake SQL**: Snowflake warehouse work. See `references/snowflake.md`.
- **T-SQL (SQL Server)**: ADF, stored procedures, meta-databases. See `references/tsql.md`.

Read the relevant reference file before writing more than trivial SQL in that dialect. Do not assume a function exists in one dialect because it exists in another. `QUALIFY`, `TOP`, `LISTAGG`, and `STRING_AGG` all differ.

## Shared style (all dialects)

- **Keywords in UPPERCASE**: `SELECT`, `FROM`, `WHERE`, `JOIN`, `GROUP BY`.
- **CTEs over nested subqueries.** A `WITH` chain reads top to bottom; nested subqueries read inside out. Prefer the former.
- **Explicit column lists. No `SELECT *`** in anything that ships. Name the columns so the shape is stable and reviewable.
- One clause per line for non-trivial queries; indent each clause body. Readability over compactness.

## Cross-dialect traps (the short list)

| Need | Databricks | Snowflake | T-SQL |
| --- | --- | --- | --- |
| Limit rows | `LIMIT n` | `LIMIT n` | `TOP (n)` or `OFFSET..FETCH` |
| Filter window func | `QUALIFY` | `QUALIFY` | no `QUALIFY`: CTE + `WHERE` on `ROW_NUMBER()` |
| String aggregate | `concat_ws` + `collect_list` | `LISTAGG` | `STRING_AGG` |
| Null fallback | `coalesce` / `nvl` | `COALESCE` / `NVL` / `IFNULL` | `COALESCE` / `ISNULL` |
| Identifier quote | `` `col` `` | `"col"` | `[col]` |

Full detail for each dialect, including the date-function argument-order traps, is in its reference file.
