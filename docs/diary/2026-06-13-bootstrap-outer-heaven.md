# Diary: Bootstrap outer_heaven

Building outer_heaven from scratch: a Claude Code plugin (skills, hooks, agents) that encodes how Benny and singularity-drone work, designed to travel across machines via git. This entry covers the bootstrap: the plugin scaffold, the SessionStart hook that injects the core profile, and the diary skill itself. It is also the first dogfood of the diary skill.

## Step 1: Plugin scaffold (Trin 0)

**Author:** singularity-drone (main)

### Prompt Context

**Verbatim prompt:** lets build
**Interpretation:** Move from the finished five-section design into building, starting with the plugin shell.
**Inferred intent:** Get a working, installable, versioned plugin skeleton onto GitHub as the foundation everything else hangs on.

### What I did
Created `.claude-plugin/marketplace.json` (marketplace `singularity-consult`) and `.claude-plugin/plugin.json` (`outer_heaven` v0.1.0), an empty `hooks/hooks.json`, the folders `skills/`, `agents/`, `docs/diary/`, `docs/insights/` (each with a `.gitkeep`), `CLAUDE.md` with the repo's own conventions and versioning discipline, and a rewritten `README.md`. Committed to `main` (`82edc69`) and pushed.

### Why
A plugin is just a manifest plus a few folders. Getting the shell in first gives every later step a place to live and makes the whole thing installable from day one.

### What worked
All JSON validated. The structure matched the Claude Code plugin layout. The commit author resolved correctly to `singularity-consult <benny@singularityconsult.dk>` via the repo-local git config, not the global `bec-systemate`.

### What didn't work
The first push attempt, run as `! git -C C:\claudes_folder\repos\outer_heaven push -u origin main`, failed with `fatal: cannot change to 'C:claudes_folderreposouter_heaven': No such file or directory`. The `!` prefix runs in Git Bash, which consumed the backslashes as escape characters. Re-running with forward slashes (`C:/claudes_folder/repos/outer_heaven`) fixed it.

### What I learned
On Windows, git paths passed through bash need forward slashes. The push authenticates through Git Credential Manager, not the gh token, and GCM keys credentials by host unless `credential.useHttpPath=true` is set.

### What was tricky
Untangling that the gh CLI account (`bechseges`) was irrelevant to the push. Setting `credential.useHttpPath=true` scoped this repo's credential to its path so it stays isolated from the `bechseges` account, which must not have write access.

### What warrants review
The marketplace name `singularity-consult` and plugin name `outer_heaven` as they read in the install commands.

### Future work
Per-machine install on Mac Mini and desktop (Trin 6).

## Step 2: SessionStart hook and core profile (Trin 1)

**Author:** singularity-drone (main)

### Prompt Context

**Verbatim prompt:** byg Trin 1 nu
**Interpretation:** Build Layer 2: the SessionStart hook that injects the locked core profile so the agent is "Benny's" from message one.
**Inferred intent:** Remove the blank-start problem so identity, tone, and standing rules load automatically every session.

### What I did
Wrote `hooks/scripts/core-profile.md` (the locked profile) and `hooks/scripts/session-start.sh`, and configured `hooks/hooks.json` with `SessionStart` entries for the `startup`, `resume`, `clear`, and `compact` matchers. Bumped the version to `0.2.0`. Added `.gitattributes` forcing LF on `*.sh` and set the executable bit on the script.

### Why
fabrik's hook is Mac-oriented and uses `jq`. It could not be reused directly here, so the script was rewritten to the most dependency-free form that still works on both Windows and Mac.

### What worked
The script ran correctly under Git Bash, parsing the version and printing the profile. The integration test confirmed the real thing: starting a session with `claude --plugin-dir C:\claudes_folder\repos\outer_heaven`, the new session identified as `singularity-drone` and quoted the marker `SessionStart:startup hook success: [outer_heaven v0.2.0 core profile]`.

### What didn't work
Two assumptions broke before the script was right. `jq` is not installed on this machine (`jq IKKE FUNDET`), so fabrik's `jq -Rs` escaping was off the table. And `bash` on PATH resolved to `C:\Users\benny\AppData\Local\Microsoft\WindowsApps\bash.exe`, the WSL stub, not Git Bash, which is too fragile to build on.

### What I learned
Verified against the Claude Code docs: SessionStart injects plain stdout straight into context, so no JSON or `jq` is needed. On Windows, Claude Code runs hook commands in Git Bash, not the WSL stub or cmd. That made a POSIX `sh` + `sed` + `cat` script the right, dependency-free choice.

### What was tricky
The CRLF risk. Git warned it would convert LF to CRLF, and a `.sh` with a `#!/bin/sh\r` shebang fails on macOS/Linux. The `.gitattributes` rule (`*.sh text eol=lf`) plus the executable bit pre-empts that for the Mac Mini.

### What warrants review
Whether the `resume`, `clear`, and `compact` matchers all behave as intended once the plugin is installed rather than loaded via `--plugin-dir`.

### Future work
Confirm the exact `/plugin` update command when the first installed version needs refreshing.

## Step 3: diary skill (Trin 2)

**Author:** singularity-drone (main)

### Prompt Context

**Verbatim prompt:** yes
**Interpretation:** Build the diary skill, the first piece of the learning loop.
**Inferred intent:** Get a durable, centralized record of work in place early, and dogfood it by documenting the bootstrap itself.

### What I did
Wrote `skills/diary/SKILL.md`, adapted from fabrik's diary pattern with two deliberate changes: diaries are centralized in the outer_heaven repo's `docs/diary/` rather than scattered per project, and a customer-confidentiality rule keeps client work at delivery level. Bumped the version to `0.3.0`, added the README entry, and wrote this diary as the first entry.

### Why
Centralizing diaries is what makes them portable across machines and aggregable by the future `work-style-insight` skill. Scattered diaries cannot be read in one sweep, which would defeat that skill entirely.

### What worked
Writing this entry confirmed the structure carries real failures well: the `jq` and WSL-stub discoveries from Step 2 are exactly the kind of tacit knowledge the format is built to retain.

### What didn't work
Nothing failed in this step. The skill is instructions, not an integration, so there was no silent-failure surface like the hook had.

### What I learned
A diary skill that lives in a plugin runs from the installed copy, but must write into the git working clone. That split needs to be stated explicitly in the skill, or diaries would land in a cache that is never committed.

### What was tricky
The path question: the working-clone location is machine-specific, so the skill records the current path and instructs the agent to locate it (or ask) rather than hardcoding a single path that breaks on other machines.

### What warrants review
Whether the diary skill triggers proactively at the right moments once installed, and not on trivial work.

### Future work
The `improve-skill` and `work-style-insight` skills (Trin 4), which consume what this skill produces.
