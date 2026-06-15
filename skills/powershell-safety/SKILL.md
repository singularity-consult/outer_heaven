---
name: powershell-safety
description: Hard rule for PowerShell script files (.ps1) in Benny's repos: never modify, overwrite, or refactor an existing .ps1 without Benny's explicit approval first. Use this whenever you are about to Edit, Write, or otherwise change a .ps1 file (deployment scripts like Deploy.ps1 especially). This is about editing .ps1 FILES, not about running normal PowerShell commands, which is fine.
---

# powershell-safety

PowerShell scripts in Benny's repos are frequently deployment and infrastructure glue. A wrong change can break a deploy or production. So the rule is hard.

## The rule

**Never modify, overwrite, refactor, or "tidy" an existing `.ps1` file without Benny's explicit approval first.** Not on your own initiative, ever.

This applies to any change: a one-line tweak, a rename, a reformat, a "harmless" cleanup. All of it is gated.

Deployment scripts (for example `Deploy.ps1`) are the highest-stakes case. Treat them as untouchable until Benny says otherwise for that specific change.

## What is and isn't covered

- **Covered (gated):** editing, overwriting, or rewriting an existing `.ps1` file.
- **Not covered (fine):** reading `.ps1` files, and running normal PowerShell commands via the shell. This skill is about changing script files, not about using PowerShell. Run PowerShell freely; just do not edit `.ps1` files unprompted.
- **New `.ps1` files:** if you genuinely need to create one, say so and why, and get a nod first when it touches deployment or infra.

## How to handle a needed change

When a `.ps1` change looks necessary:

1. Stop before editing.
2. Show Benny the exact change (the diff, or the precise lines) and why it is needed.
3. Wait for explicit approval for that specific change.
4. Only then edit.

A hard `PreToolUse` hook that blocks `.ps1` edits outright is a planned reinforcement of this rule, so the guardrail does not rest on memory alone.
