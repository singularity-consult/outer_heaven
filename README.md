# outer_heaven

How Benny and singularity-drone build.

A Claude Code plugin that bundles the skills, hooks, and agents for a consistent way of working: a portable, versioned configuration that travels across machines.

## Install

```shell
/plugin marketplace add singularity-consult/outer_heaven
/plugin install outer_heaven@singularity-consult
```

## Structure

- `skills/`: all skills
- `agents/`: sub-agents
- `hooks/`: session-start context injection and other hooks
- `docs/diary/`: implementation diaries
- `docs/insights/`: work-style insights

## Available skills

- **diary**: Implementation diary in the outer_heaven repo, capturing what changed, why, what worked, what failed, and what was tricky. Activates during non-trivial work and at session-end moments.
- **git**: Git conventions for Benny's repos: commit author identity per repo (never Co-Authored-By or Claude), context-dependent branch naming, English commit messages.
- **improve-skill**: Review the current conversation for outer_heaven skills that underperformed (corrections, missed triggers, friction) and ship fixes back via a lightweight branch-and-push flow. User-invoked, or suggested at session end only when there is concrete signal.
- **merge-conflict-safety**: Resolve merge conflicts safely: `git log main..branch --stat` first, keep only the branch's real changes, take `main` for everything else.
- **powershell-safety**: Hard rule: never modify an existing `.ps1` file without Benny's explicit approval first. Reading and running PowerShell is fine.
- **python**: Python conventions for Benny's work (Databricks/PySpark, pandas, pipeline libraries, FastAPI): PEP 8 style and idiom, type hints, structure, and the traps that bite most (mutable defaults, chained assignment, Spark laziness).
- **sql**: SQL conventions and dialect guidance for Databricks SQL, Snowflake SQL, and T-SQL (UPPERCASE keywords, CTEs, explicit columns). Dialect-specific syntax and gotchas in `references/`.
- **terraform**: Terraform/IaC conventions and safety for Benny's Azure repos: plan before apply, prod needs approval, never commit secrets or state, pin versions, `fmt`/`validate`.
- **work-style-insight**: Read the diary corpus in `docs/diary/` and distil patterns in how Benny works and decides, plus derived suggestions, into a dated file in `docs/insights/`. User-invoked; never edits skills itself.
- **writing-clearly-and-concisely**: Apply Strunk's *Elements of Style* to prose a human reads (docs, commit messages, errors, UI copy): omit needless words, active voice, concrete language.

## Available sub-agents

- **builder**: Takes requirements and ships the work in the lead's worktree, validating it before handing back. Validation-centered for Benny's stack (Databricks/PySpark, Python, SQL, Terraform/IaC, ADF, Power BI).
- **lead**: Refines an idea into concrete requirements, challenges assumptions, manages scope, and runs the builder team in an isolated worktree. Does not implement.
