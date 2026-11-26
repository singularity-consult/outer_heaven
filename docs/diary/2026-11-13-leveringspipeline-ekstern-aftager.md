# Diary: Fixed delivery pipeline for an external consumer (SEGES DataEstate2026)

Goal: add a fixed delivery step to the delivery job in the new data estate, so the daily JSON files are copied to the external consumer's storage with the same names and format as the old estate. Builds on an existing feature branch where file parity was already achieved and a one-off delivery test proved network and auth from serverless compute.

## Step 1: Requirements and hand-off to builder

**Author:** lead

### Prompt Context

**Verbatim prompt:** (sanitised) Benny har bedt om at få bygget den faste leveringspipeline for en ekstern aftager i nyt estate (SEGES, repo C:\claudes_folder\repos\DLBR-DataEstate2026). Du styrer builder-teamet; du implementerer ikke selv. (Remainder of the main agent's brief: build on the fix branch, deliver the daily JSON files to the consumer container with exact old file names, guard against missing/empty/too small files, idempotent reruns, target account and path prefix configurable per environment because the target decision is still open, no PR, no release, no job runs.)
**Interpretation:** Turn the proven one-off test script into a governed task in the delivery job, with per-environment configuration that does not lock the open decision about which account production writes to.
**Inferred intent:** Make the cutover from the old estate a configuration flip rather than a code change, and make it impossible to deliver half data.

### What I did
Read the project status file, the delivery job workflow, an integration notebook, the old estate's copy step and mount notebook, and exported the one-off test script from the dev workspace. Listed secret names in the dev secret scope (the three consumer secrets exist). Tried to list the test and prod scopes. Reset the lead worktree branch to the fix branch on origin (the named branch is checked out in another worktree, so pushes go via HEAD:<fix branch>). Spawned one builder.

### Why
The target account is not yet decided, so it is configurable per environment and delivery is disabled by default.

### What worked
The test script gave exact secret names and the SDK approach; the old estate code gave the path layout, so the new step uses the same path layout as the old estate.

### What didn't work
`databricks secrets list-secrets <scope> --profile test` -> "A new access token could not be retrieved because the refresh token is invalid." Same for prod. `az keyvault secret list --vault-name <kv>` -> first "AKV10032: Invalid issuer" (wrong default tenant), then with `--subscription` -> "(Forbidden) Caller is not authorized to perform action on resource." Running `databricks workspace export` from Git Bash rewrote the `/Workspace/...` path to a Windows path; PowerShell worked. Writing this diary into the outer_heaven clone was refused by the worktree isolation guard, so it was drafted in the scratchpad and handed to the main agent.

### What I learned
The JSON output directory is overwritten daily, so yesterday's file is not available locally for a relative size guard; the previous version of the integration Delta table is the natural baseline.

### What was tricky
The target account is not yet decided, so it is configurable per environment and delivery is disabled by default. Pausing schedules is not enough; delivery needs an explicit per-environment enable flag.

### What warrants review
That the enable flag defaults to off in every environment until the cutover decision, and that the guard compares against a sensible baseline.

### Future work
Verify secrets in test/prod scopes and serverless egress from prod before cutover.
