---
name: powershell-safety
description: Hard rule for PowerShell script files (.ps1) in Benny's repos: never modify, overwrite, or refactor an existing .ps1 without Benny's explicit approval first. Use this whenever you are about to Edit, Write, or otherwise change a .ps1 file (deployment scripts like Deploy.ps1 especially). This is about editing .ps1 FILES, not about running normal PowerShell commands, which is fine. Also covers authoring PowerShell snippets you hand Benny to paste and run interactively, so terminal line-wrapping does not corrupt them.
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

## Authoring PowerShell you hand Benny to paste

Separate from editing `.ps1` files: when you give Benny PowerShell to paste and run interactively, write it so terminal line-wrapping at the `>>` continuation prompt cannot silently corrupt it. A wrapped line injects a newline plus indentation into whatever it lands in.

- **Pull any token with internal spaces into its own short variable**, then reference the variable. A long literal that wraps mid-token breaks silently. Real case: a wrapped `Driver={IBM DB2 ODBC DRIVER - C_DB2CLI}` connection string produced `ERROR [IM002] Data source name not found` until the driver name was pulled into `$drv` first.
- **Build long strings in short pieces with `+=`**, one keyword per physical line, instead of one long line that wraps unpredictably. A connection string split as `$cs = "Driver={$drv};Hostname=...;Port=...;"` then `$cs += "Database=...;..."` survives the paste; a single 200-char line does not.
- **Keep each physical line short** enough not to wrap, and never split a single quoted literal across the visual wrap.
- These are paste-robustness habits, not a license to touch `.ps1` files; the hard rule above still applies to anything saved as a script.

