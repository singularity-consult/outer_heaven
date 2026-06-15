---
name: python
description: Python conventions for Benny's work (data engineering on Databricks/PySpark and pandas, pipeline libraries, FastAPI services). Use this whenever you read or write Python. Covers style and idiom, type hints, structure, and the traps that bite most often. Kept general; context-specific detail (PySpark vs pandas vs API) is followed from the surrounding code, not duplicated here.
---

# python

Benny writes a lot of Python: PySpark and pandas in Databricks, modular pipeline code (for example the Grundfos matching pipeline), and FastAPI services. This skill is the standing style and the traps. It does not restate the docs; it captures how we want the code to read and the mistakes worth naming.

## Style and idiom

- **Follow PEP 8.** 4-space indent, `snake_case` for functions and variables, `PascalCase` for classes, `UPPER_SNAKE` for constants. Let the formatter settle layout; do not hand-align.
- **Match the surrounding code first.** Notebook cells, a pipeline package, and a FastAPI app each have a house style. The repo wins over a general rule.
- **Idiomatic, not clever.** Comprehensions over `map`/`filter` when they stay readable; a plain loop when the comprehension would not. F-strings for formatting. Context managers (`with`) for files, connections, and locks.
- **No bare `except:`.** Catch the specific exception. A bare except swallows `KeyboardInterrupt` and hides real failures.
- **`pathlib.Path` over string paths** for filesystem work.

## Type hints

- **Annotate public functions** (signatures and return types) in library and pipeline code. Hints are documentation and they let the reader and the type checker catch shape errors early.
- Notebook exploration can stay loose; production modules should not.
- Prefer modern syntax on the target's Python version: `list[str]`, `dict[str, int]`, `X | None`. Reach for `typing` (`Optional`, `Union`, `Iterable`) only when the runtime is older.

## Structure

- **Small, single-purpose functions.** The Grundfos pipeline's loader -> normalizer -> blocker -> scorer -> resolver -> writer split is the pattern: each stage does one thing and is testable on its own.
- **Pure core, side effects at the edges.** Keep I/O (read, write, network) at the boundary; keep transformation logic pure so it can be tested without a cluster or a database.
- **`if __name__ == "__main__":`** guards script entry points so a module stays importable.
- **Dependencies are explicit.** Pin in `requirements.txt` / `pyproject.toml`. No reliance on whatever happens to be on the cluster.

## Traps worth naming

- **Mutable default arguments.** `def f(x, acc=[])` shares one list across calls. Use `acc=None` then `acc = acc or []`.
- **pandas chained assignment.** `df[df.a > 0]['b'] = 1` writes to a copy and may do nothing. Use `.loc[mask, 'b'] = 1`.
- **PySpark is lazy.** Transformations build a plan; nothing runs until an action (`count`, `collect`, `write`). Do not expect a `withColumn` to fail at the line you wrote it. Avoid `collect()` on large frames: it pulls everything to the driver and OOMs it.
- **pandas vs PySpark are not interchangeable.** Same intent, different API. Do not assume a pandas method exists on a Spark DataFrame.
- **Integer/float and NaN.** A pandas column with a NaN becomes float; an "int" column can silently carry `1.0`. Cast deliberately when the downstream cares.
- **Timezone-naive datetimes.** Mixing naive and aware datetimes raises or compares wrong. Be explicit about tz.

## Note

When a repo shows a convention this skill does not capture (a project's lint config, a preferred PySpark idiom, an API structure), follow the repo and flag it for adding here.
