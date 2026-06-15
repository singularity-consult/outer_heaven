---
name: merge-conflict-safety
description: How to resolve git merge conflicts safely in Benny's repos: before resolving, run `git log main..branch --stat` to see which files the branch actually changed, keep only those, and take main for everything else. Use this whenever you hit a merge conflict or are about to resolve one. Prevents git rename confusion from injecting wrong content, especially into .yml files.
---

# merge-conflict-safety

Merge conflict resolution in Benny's repos has bitten before: git's rename detection can inject the wrong content into files (especially `.yml`), and a careless resolution keeps changes that should have stayed on `main`. This skill is the safe procedure.

## Before resolving anything

Run:

```
git log main..branch --stat
```

This shows exactly which files the branch genuinely changed. That list is your scope: those are the only files where the branch's version should win.

## The rule

- **Keep only the branch's real changes**, the files listed by `git log main..branch --stat`.
- **Take `main` for everything else.** If a file is in conflict but the branch never meaningfully touched it, its content should come from `main`, not from the merge's guess.
- This protects against git rename confusion, where rename detection injects unrelated or wrong content into a file (`.yml` files have been hit this way).

## Fixing a file that got the wrong content

If a file ended up with wrong or injected content during resolution, reset it to main's version:

```
git checkout main -- <file>
```

Then re-apply only the branch's intended change to that file, if there was one.

## Why this matters

A merge conflict is not an invitation to merge everything the tool offers. The branch has a small, knowable set of real changes; the `--stat` diff makes that set explicit so you keep exactly those and nothing else.
