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
- **merge-conflict-safety**: Resolve merge conflicts safely: `git log main..branch --stat` first, keep only the branch's real changes, take `main` for everything else.
- **powershell-safety**: Hard rule: never modify an existing `.ps1` file without Benny's explicit approval first. Reading and running PowerShell is fine.
- **writing-clearly-and-concisely**: Apply Strunk's *Elements of Style* to prose a human reads (docs, commit messages, errors, UI copy): omit needless words, active voice, concrete language.

## Available sub-agents

None yet. Build in progress.
