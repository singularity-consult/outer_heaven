---
name: git
description: Conventions for git in Benny's repos: never add Co-Authored-By or set Claude as commit author, resolve the right author identity per repo (own/Singularity vs SEGES/customer), context-dependent branch naming, and English commit messages. Use this whenever you branch, commit, or write a commit message, not only when explicitly asked to "commit". These conventions are not in your default knowledge and you will get them wrong without consulting this skill.
---

# git

Most git usage is what you already know. This skill is the set of refinements specific to how Benny works: the parts you would otherwise get wrong.

## Commit author: never Claude, never the wrong identity

- **Never** add a `Co-Authored-By` line, and never set Claude (or any AI) as the commit author. Commits are authored by Benny, full stop.
- **Resolve the author identity by repo context:**
  - **Own / Singularity repos** (for example outer_heaven, Datavilla): `singularity-consult <benny@singularityconsult.dk>`.
  - **SEGES / customer repos** (DLBR, o90, Databricks work): `Benny Christiansen <bech@seges.dk>`.
- **Never** use `bec-systemate` (the global default `bec-systemate <bec@systemate.dk>`) as the commit author anywhere. It is wrong in every repo.
- The identity is set per repo via repo-local `git config user.name` / `user.email`, so it does not depend on the global config. After committing, if there is any doubt about which identity a repo uses, verify with `git log -1 --format="%an <%ae>"`.
- The specific repos that pin a particular identity live in memory, not here. This skill is the general rule; memory holds the exceptions.

## The gh CLI is a separate identity

Commit author identity (set per repo) is not the same as which account `gh` acts as. `gh` is a single-active-account tool, and on Benny's machine it defaults to `bechseges`, which has no access to the `singularity-consult` repos (outer_heaven, command-deck).

- **Releases, PRs, and repo creation on a singularity-consult repo need the singularity-consult account active.** Switch first: `gh auth switch -u singularity-consult` (and back with `gh auth switch -u bechseges` for SEGES work). Both accounts can be logged in at once.
- A failing `gh release create` / `gh pr create` that says `"workflow" scope may be required` is usually **not** a scope problem; it is the active account lacking access to that repo. Check `gh auth status` before chasing scopes.
- Plain `git push` does not have this problem: it uses the per-path stored credential (Git Credential Manager with `credential.useHttpPath=true`), so it pushes as the right account without a prompt. This is why the improve-skill flow avoids `gh pr create` and hands back a compare URL.

## Branch naming

Context-dependent:

- **SEGES / customer repos:** prefix by type: `feature/`, `hotfix/`, `fix/`, `release/` (for example `feature/o90-add-kredsnr`, `hotfix/fix-ested-primary-key`, `release/release_20260602`).
- **Own repos** (outer_heaven, Datavilla): a short dash-sentence, no prefix (for example `add-work-style-insight`).

On a customer repo, work on a branch; do not commit straight to the default branch. On own repos, small bootstrap work can go straight to `main`, but changes to outer_heaven skills go through a branch and PR (the self-review checkpoint before a skill change reaches every future session).

## Commit messages

- **Language: English** in commits and code artifacts. Prose and conversation stay Danish.
- Concise and readable for someone skimming `git log`, not studying the diff. Lead with what changed in plain language. Deeper context belongs in the diary, not the commit message.
- Wrap code identifiers in backticks where it aids readability, for example "Add `diary` skill". Watch the shell when committing: in **PowerShell** a literal backtick is the escape character and must be doubled (write `` ``0.4.0`` `` to get `` `0.4.0` ``); in **bash/sh** a backtick inside double quotes triggers command substitution, so use single quotes or a heredoc.
- Reference GitHub issues at the end when relevant: "See #123", or to auto-close use "Fixes #123".

## Timing and safety

- Commit or push only when Benny asks. Building or editing files is not itself a commit request.
- Confirm before destructive or hard-to-reverse operations: `git reset --hard`, `git push --force`, branch deletion, history rewrites.
- For merge conflicts, check `git log main..branch --stat` before resolving so only the branch's real files are kept (a dedicated `merge-conflict-safety` skill covers this in full).
