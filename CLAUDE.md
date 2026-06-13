# outer_heaven

A Claude Code plugin (marketplace `singularity-consult`) that bundles skills, hooks, and agents: how Benny and singularity-drone build.

This repo holds workflow capabilities and collaboration improvements only. It does NOT hold project knowledge or sensitive personal information.

## What lives here, and what does not

- IN: skills, hooks, agents, and the diary/insight artifacts that should travel across machines.
- OUT: project status and knowledge (stays in memory), and sensitive personal information (health, finance, private projects) which never enters this repo.
- Customer repos hold only their solutions. No agent data is ever committed to a customer repo. Diaries about customer work stay at delivery level (name the project, keep customer-confidential detail out).

## Structure

- `.claude-plugin/`: marketplace.json + plugin.json (the plugin version lives in plugin.json)
- `skills/`: all skills, one folder per skill with a SKILL.md
- `agents/`: sub-agents
- `hooks/`: hooks.json + scripts (session-start context injection)
- `docs/diary/`: implementation diaries (delivery level; customer-confidential detail kept out)
- `docs/insights/`: work-style insights about Benny (created when the work-style-insight skill runs)

## Core principles

- Skills are the source of truth for how we work. MEMORY.md points at skills rather than restating their content.
- Always-on behavior (identity, tone, standing rules) lives in the SessionStart hook. Situational guidance lives in skills.
- Diaries are centralized here so they can be read in one sweep and travel across machines via git.

## Adding a new skill or sub-agent

When adding a skill or sub-agent, also add a one-line entry to README.md in the same commit: skills under "Available skills", sub-agents under "Available sub-agents". Both lists are alphabetical and use the format `- **name**: one-line description`.

## Versioning

Bump the version in `.claude-plugin/plugin.json` after any change that should reach the installed copies. Remote installs are cached by version: without a bump, updates do not propagate.

- New functionality (a new skill, sub-agent, or hook) is a minor bump.
- Changes to existing functionality are a patch bump.

Each version should also get a git tag (for example `v0.1.0`) on the version-bump commit, pushed, with a GitHub release.
