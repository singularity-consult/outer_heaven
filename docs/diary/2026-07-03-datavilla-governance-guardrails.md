# Diary: Datavilla governance/guardrail block (cluster policy, tagging, budgets)

Add a minimum-cost governance layer to the private `datavilla` project entirely as
IaC: per-environment Databricks cluster policies that force cheap single-node spot
job clusters, a three-layer automatic tagging scheme, Azure budgets per env RG, and
job-generator integration so generated clusters bind the policy. Ledestjerne:
absolute minimum cost (privately paid, tiny data, spot confirmed OK). Deliver diffs
to main; main deploys per env and commits. No commits, no apply against Azure.

## Step 1: Build the full guardrail block across infra/, platform/ and src/

**Author:** outer_heaven:builder

### Prompt Context

**Verbatim prompt:** Byg en governance/guardrail-blok til datavilla: cluster policies (minimum cost), automatisk tagging, og Azure budgets — alt IaC. Bennys eget projekt. Følg `terraform`-skillen. Aflever diffs til main; main deployer per miljø + committer. INGEN commits, INGEN apply/deploy mod Azure. (Full task: 4 opgaver — cluster policy per miljø, tagging i tre lag, Azure budgets per RG, job-generator integration — plus grænser/aflevering as specified.)

**Interpretation:** Implement four IaC deliverables in the datavilla repo, validate offline (fmt, validate -backend=false, pytest), and hand back diffs with an explicit apply/wire-up plan for main. Do not run any backend init/plan/apply/commit.

**Inferred intent:** Give the privately-paid datavilla project a cost safety net that is enforced (not advisory) and self-consistent across the three roots, so Benny cannot accidentally spin up expensive clusters and gets alerted before a bill runs away.

### What I did
Read the three roots first (infra/, platform/, src/) end to end before touching anything. Then:

- **Opgave 1 — cluster policy (infra/):** new `infra/cluster_policy.tf` with one `databricks_cluster_policy` (workspace provider) per infra apply. Definition is `jsonencode` of an HCL object: `spark_version` allowlist (LTS 15.4.x only), `node_type_id` allowlist per env, `num_workers` fixed 0 + `spark_conf.spark.databricks.cluster.profile`=singleNode + `spark_conf.spark.master`=local[*] (the canonical single-node trio), `azure_attributes.first_on_demand`=0 + availability=SPOT_WITH_FALLBACK_AZURE, `runtime_engine`=STANDARD (Photon off), `autotermination_minutes` range maxValue 10, and forced `custom_tags` (project/environment/ResourceClass fixed; `source` type `unlimited` + `isOptional=false` so the key is required but the value is per-job). Node type is parametrised: `allowed_node_type_ids` per env tfvars.
- **Opgave 2 — tagging in three layers:** extended `local.tags` in `infra/main.tf` to the full taxonomy (project/environment/managed_by/cost_center/owner; `source` excluded because it is compute-specific). Verified every taggable azurerm resource in infra already receives `local.tags` via module inputs — containers/subnets/NSG-associations/Databricks objects are not taggable, so nothing was missing. Added `azurerm_resource_group_policy_assignment` (built-in "Inherit a tag from the resource group", GUID `cd3aa116-8754-49c9-a813-ad46512ece54`) in new `infra/tag_inheritance.tf`, one per mandatory tag × two scopes (env RG + the Databricks-managed RG), each with a SystemAssigned identity and a Contributor role assignment on its scope. Also mirrored `local.tags` into `platform/main.tf` (environment="global") with variables, noting no current platform resource is taggable.
- **Opgave 3 — budgets (infra/):** new `infra/budget.tf` — `azurerm_consumption_budget_resource_group` per env RG, amount via `budget_amount` (dev/test 150, prod 300 DKK), four notifications (80/100% × Forecasted/Actual) to benny@singularityconsult.dk.
- **Opgave 4 — job generator (src/):** updated `JOB_TEMPLATE` in `scripts/generate_jobs.py` — node type `Standard_F4s_v2`, `num_workers` 0, `policy_id: ${var.cluster_policy_id}`, singleNode spark_conf, spot azure_attributes, STANDARD runtime, `custom_tags` with `source: "<name>"` + ResourceClass. Added the `cluster_policy_id` bundle variable to `src/databricks.yml`. Regenerated the 4 committed job ymls.
- **Supporting outputs/vars:** added `id` output to the resource_group module, `managed_resource_group_id` to the databricks module, a new `infra/outputs.tf` (cluster_policy_id + refs), and all the new infra/platform variables.

Validation: `python scripts/generate_jobs.py` (regenerated 4), `python -m pytest -q` (26 passed), `terraform fmt -recursive` both roots, `terraform init -backend=false` + `terraform validate` both roots (both "Success! The configuration is valid.").

### Why
Cost enforcement has to be a policy the runtime rejects violations against, not a convention — hence a Databricks cluster policy with fixed/allowlist elements rather than just a cheap default in the job YAML. Tagging needs the inherit-from-RG Azure Policy specifically because the Databricks-managed RG's VMs/disks are created outside Terraform and can't be tagged from HCL. Budgets are the last-resort net if the policy is ever bypassed.

### What worked
Node-type choice was verified, not guessed: web search confirmed Databricks' documented minimum is 4 cores / 8192 MB, which `Standard_F4s_v2` (4 vCPU / 8 GiB) hits exactly — anything smaller (F2s_v2) is below the floor. The inherit-tag policy GUID, its `modify` effect, `tagName` parameter, and Contributor roleDefinitionId were all confirmed against azadvertizer before wiring. `terraform validate` passing on both roots means all the cross-module references (managed_resource_group_id, resource_group.id, the setproduct-driven for_each map, the policy-assignment identity/role chain) resolve.

### What didn't work
No hard failures. Two expected non-failures worth noting: (1) after editing the template, `test_committed_jobs_are_up_to_date` would have failed until I regenerated — the generator owns those files, so regenerating was the correct response, not a bug. (2) `terraform fmt` reformatted `cluster_policy.tf` (aligned the map `=`); cosmetic only.

### What I learned
The generator template is a Python `.format` string, so every literal brace must be doubled — `${{var.cluster_policy_id}}` renders to `${var.cluster_policy_id}`. `local[*]` and the dotted `spark_conf.*` keys have no braces, so they pass through untouched; I confirmed by reading the regenerated yml rather than trusting it.

### What was tricky
The tag-inheritance remediation timing is the sharp edge. The built-in policy is `modify`, so new resources get tagged on create once the assignment+identity+Contributor role exist, but EXISTING managed-RG resources need a remediation task — and Azure's compliance scan is asynchronous (can be ~30 min after assignment), so a Terraform remediation resource created in the same apply typically finds nothing to remediate. I deliberately did NOT codify a TF remediation; instead this is a manual step for main (`az policy remediation create` per assignment after the scan). Also unverifiable here: whether the Databricks-managed RG actually carries the workspace tags for the policy to inherit from (Databricks propagation behaviour) and whether the RG's CanNotDelete lock interferes with creating the policy/role assignment on it.

### What warrants review
Look at `infra/tag_inheritance.tf` (scope choice env-RG + managed-RG, and the Contributor grant breadth), and confirm with main the apply order: platform → infra (per env, with `-var service_principal_application_id=...`) → `terraform -chdir=infra output -raw cluster_policy_id` → `databricks bundle deploy --var cluster_policy_id=<id>` per target → manual `az policy remediation create` for pre-existing resources. Budget `start_date` defaults to 2026-07-01 and must be the first of the current month at apply. Everything touching the live Databricks workspace / Azure control plane is apply-time-unverified because no apply was run.

### Future work
Confirm at apply whether the managed RG inherits tags as expected; if not, the fallback is to set tags explicitly on the workspace's managed RG or move the inherit assignment to subscription scope. Consider whether prod's F8s_v2 ceiling is ever actually needed or can be dropped to keep prod at F4s_v2 too.
