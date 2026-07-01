# Diary: Datavilla Key Vault RBAC + platform identity root

Two separate Terraform tasks in Benny's own `datavilla` project. Benny is already Owner on subscription `83d6730c-...` but lacks data-plane access: the Key Vault runs the access-policy model with 0 policies, so not even Owner can read secrets. Fix is to switch the vault to the RBAC model, and grant data-plane access via an Entra group assigned at subscription scope from a new, separate `platform/` Terraform root.

## Step 1: Key Vault to RBAC + new platform/ identity root

**Author:** builder

### Prompt Context

**Verbatim prompt:** To adskilte Terraform-opgaver i datavilla-projektet. OPGAVE 1 — sæt `enable_rbac_authorization = true` på `azurerm_key_vault` i `infra/modules/keyvault/`, rør intet andet, kør ikke init/plan/apply. OPGAVE 2 — opret selvstændig `platform/`-rod (versions/providers/backend/variables/main/outputs/terraform.tfvars) med azurerm ~> 4.0 + azuread (nyeste stabile major, pin), azuread-gruppe `datavilla-platform-admins` (security-enabled, assignable_to_role=false), admin-medlem, og to subscription-scope role_assignments (Key Vault Administrator, Storage Blob Data Owner) på gruppens object_id med principal_type="Group". Rør ikke Bennys personlige Owner-tildeling. Valider med fmt + `validate` under `init -backend=false` i begge rødder; ingen backend-init, plan, apply eller git-commit.

**Interpretation:** One small edit in the existing workload root (`infra/`) to flip the vault authorization model, plus a brand-new standalone platform/identity root that provisions the Entra group and the two subscription-scope RBAC role assignments. Validation is fmt + offline validate only; no state, no apply, no commit.

**Inferred intent:** Give Benny (and future admins) real data-plane access to Key Vault secrets and storage blobs without hand-clicking in the portal, while keeping subscription-level identity/RBAC cleanly separated from workload IaC and preserving the personal Owner assignment as break-glass.

### What I did

OPGAVE 1: In `infra/modules/keyvault/main.tf`, added the RBAC flag to the `azurerm_key_vault.this` resource. I initially wrote the task-specified `enable_rbac_authorization = true`, but `terraform validate` under the pinned azurerm `~> 4.0` flagged it as deprecated (see What didn't work), so I switched to the canonical current name `rbac_authorization_enabled = true`. Nothing else in `infra/` touched.

OPGAVE 2: Created `C:\claudes_folder\repos\datavilla\platform\` with seven files: `versions.tf` (required_version >= 1.0; azurerm ~> 4.0, azuread ~> 3.0 — 3.x is the latest stable azuread major), `providers.tf` (azurerm with empty `features {}` + `subscription_id = var.subscription_id`; bare `provider "azuread" {}` for CLI auth), `backend.tf` (azurerm backend, same storage as infra, fixed `key = "datavilla-platform.tfstate"`, no partial backend), `variables.tf` (`subscription_id`, `admin_upn` default `benny@singularityconsult.dk`, `group_name` default `datavilla-platform-admins`), `main.tf` (`data azuread_user`, `azuread_group` security-enabled + `assignable_to_role = false`, `azuread_group_member`, `data azurerm_subscription current`, two `azurerm_role_assignment` at subscription scope with `principal_id = azuread_group.platform_admins.object_id` and `principal_type = "Group"`), `outputs.tf` (group object_id + display_name), and `terraform.tfvars` (subscription_id only). Benny's personal Owner assignment is not represented in Terraform and was left entirely alone.

Validation: `terraform fmt` in both roots (no reformatting needed). `terraform init -backend=false` then `terraform validate` in each root separately — both report `Success! The configuration is valid.`

### Why

Splitting platform/identity from workload keeps subscription-scope RBAC and Entra group lifecycle out of the per-environment `infra/` state, which is the correct blast-radius boundary. Granting via a group rather than to Benny directly means future admins get access by group membership, not by re-running RBAC. The vault RBAC flip is the prerequisite: with the access-policy model and 0 policies, the subscription-scope Key Vault Administrator role would have no effect on the data plane.

### What worked

fmt was a no-op on all files (formatting canonical on first write). Offline validate under `init -backend=false` worked cleanly in both roots without touching remote state, exactly as intended — the platform root pulled providers fresh (no lockfile yet) and still validated.

### What didn't work

First `terraform validate` on infra surfaced a deprecation warning, verbatim:

```
Warning: Argument is deprecated
  with module.keyvault.azurerm_key_vault.this,
  on modules\keyvault\main.tf line 10, in resource "azurerm_key_vault" "this":
  10:   enable_rbac_authorization = true
This property has been renamed to `rbac_authorization_enabled` and will be removed in v5.0 of the provider
```

Config was still valid, but under the pinned `~> 4.0` provider the old name is deprecated and breaks at v5. Fixed by renaming to `rbac_authorization_enabled = true`; re-ran `terraform fmt && terraform validate` → clean `Success! The configuration is valid.` no warnings.

### What I learned

azurerm 4.x renamed the Key Vault authorization flag from `enable_rbac_authorization` to `rbac_authorization_enabled`. Same behavior, but the old name is deprecated in 4.x and removed in 5.0. Worth remembering for any other vaults in Benny's 4.x repos.

### What was tricky

The task text named the deprecated attribute explicitly, so I had to make a judgment call to deviate to the non-deprecated name. It is behaviorally identical and forward-compatible under the pinned provider, so I went with the clean name and flagged the deviation.

### What warrants review

The azuread group creation and membership are only offline-validated — `validate` confirms schema/config correctness but cannot confirm the apply will succeed. Creating an Entra group requires directory permissions in the tenant (Groups Administrator, or that group creation is permitted for the caller). That is an apply-time unknown, not something resolvable here. Reviewer should also confirm the intended deviation from the prompt-named `enable_rbac_authorization` to `rbac_authorization_enabled` is acceptable, and that `azuread ~> 3.0` is the pin Benny wants.

### What didn't work (validation gaps)

Beyond the deprecation warning above: nothing. No plan/apply was run by design, so runtime behavior (group creation, role assignment against a live subscription) is unverified.

### Future work

At apply time (handled by main): backend init for the platform root, then plan and read it line by line before apply; confirm directory permissions allow group creation; verify the two role assignments land on the group's object_id at subscription scope. Infra apply flips the vault to RBAC across dev/test/prod.

## Step 2: Unity Catalog access control (per-env groups + Entra SPs, workspace binding, authoritative grants)

**Author:** builder

### Prompt Context

**Verbatim prompt:** Byg Unity Catalog adgangsstyring for datavilla som IaC: per-miljø grupper + Entra service principals, workspace-binding for miljø-isolation, og autoritative grants. [...] OPGAVE A — `platform/`: Databricks account-provider + per-miljø (for_each over dev/test/prod) `databricks_group` `datavilla_<env>_analysts`, `azuread_application` + `azuread_service_principal` (display `datavilla-<env>-sp`), `databricks_service_principal` (account) med `application_id = azuread_application.client_id`; outputs map miljø→SP application_id og miljø→gruppenavn; variabel `databricks_account_id`. OPGAVE B — `infra/modules/unity_catalog`: `isolation_mode = "ISOLATED"`, `databricks_workspace_binding` for de 6 catalogs mod miljøets eget workspace (`workspace_numeric_id`), grants i dedikeret `grants.tf` (autoritativt, `databricks_grants`): analysts kun curated+integration (USE_CATALOG/USE_SCHEMA/SELECT), SP alle 6 (USE_CATALOG/USE_SCHEMA/CREATE_SCHEMA/CREATE_TABLE/MODIFY/SELECT, IKKE ALL/MANAGE), benny@singularityconsult.dk alle 6 (ALL_PRIVILEGES). fmt + validate under init -backend=false i begge rødder, STOP før apply, ingen git-commits.

**Interpretation:** Extend the same `platform/` root with a Databricks account provider and per-env identity objects (account groups + Entra-registered SPs registered back into the Databricks account), and expose them as outputs. In the `unity_catalog` module, turn on catalog isolation, bind each catalog to its own workspace, and lay down authoritative grants in a dedicated file. Wire the new module inputs through `main.tf`/`variable.tf`/tfvars. Offline validation only.

**Inferred intent:** Give each environment (dev/test/prod) an isolated, least-privilege access model on the shared regional metastore: analysts read only the business layers, an automation SP can build/load but not re-grant or re-own, and Benny keeps full control — all reproducible as code and separated so identity lifecycle lives in `platform/` while catalog-scoped grants live with the catalogs in `infra/`.

### What I did

OPGAVE A — `platform/`: added the `databricks` provider to `versions.tf` (`~> 1.0`); added a `databricks.account` provider alias in `providers.tf` (host `https://accounts.azuredatabricks.net`, `account_id = var.databricks_account_id`, `auth_type = "azure-cli"` to match the existing azurerm/azuread CLI auth); added `variable "databricks_account_id"` (default `383270ab-...`). In `main.tf` added a `locals.environments = toset(["dev","test","prod"])` and four `for_each` resources over it: `databricks_group.analysts` (account provider, display `datavilla_<env>_analysts`), `azuread_application.env_sp` (display `datavilla-<env>-sp`), `azuread_service_principal.env_sp` (`client_id = azuread_application...client_id`), and `databricks_service_principal.env_sp` (account provider, `application_id = azuread_application...client_id`). Added two outputs: `service_principal_application_ids` (env→client_id) and `analyst_group_names` (env→display name).

OPGAVE B — `infra/modules/unity_catalog/`: on `databricks_catalog.layers` added `isolation_mode = "ISOLATED"`. Added `databricks_workspace_binding.layers` (`for_each = databricks_catalog.layers`, `securable_type = "catalog"`, `workspace_id = var.workspace_numeric_id`, `binding_type = "BINDING_TYPE_READ_WRITE"`). New module vars in `variables.tf`: `workspace_numeric_id` (number), `service_principal_application_id` (string), `analysts_group_name` (string), `admin_principal` (string, default `benny@singularityconsult.dk`). New dedicated `grants.tf` with `databricks_grants.layers` (`for_each` over the catalogs, workspace provider): SP grant on all 6, admin ALL_PRIVILEGES on all 6, and a `dynamic "grant"` for the analysts group gated on `contains(["curated","integration"], each.key)`. Wired `main.tf`: module call now passes `workspace_numeric_id = module.databricks.workspace_numeric_id`, `service_principal_application_id = var.service_principal_application_id`, and `analysts_group_name = "${replace(local.name_suffix, "-", "_")}_analysts"` (derived, see Why). Added top-level `variable "service_principal_application_id"` (default `""`) in `variable.tf` and a documented placeholder comment block in each of dev/test/prod.tfvars.

Validation: `terraform fmt` in both roots (no reformatting needed). `terraform init -backend=false` then `terraform validate` in each root — both `Success! The configuration is valid.` The init added the `databricks` provider hash to `platform/.terraform.lock.hcl` (expected).

### Why

Cross-state mechanic (the crux): the SP `application_id` is a GUID that only exists after `platform/` is applied, so it cannot live statically in `infra/`. I chose the explicit path the task nudged toward — `platform/` exposes it as an output, and main feeds it into `infra/` per env via `-var` at apply time — rather than a hidden `terraform_remote_state` coupling that silently reorders the roots. tfvars carry only a documented placeholder. The analyst group name, by contrast, is fully deterministic (`datavilla_<env>_analysts`), so I derive it in `main.tf` from `local.name_suffix` instead of adding a redundant tfvars line; this keeps it structurally in sync with the name `platform/` actually creates (`datavilla-dev` → replace `-`→`_` → `datavilla_dev` → `_analysts`). `databricks_grants` (plural) is authoritative so Terraform owns the whole grant list and reverts drift; the SP deliberately gets no `ALL_PRIVILEGES`/`MANAGE` so automation cannot change ownership or re-grant.

### What worked

fmt was a no-op in both roots. Offline `validate` under `init -backend=false` passed in both roots and, importantly, validated every new resource against the freshly downloaded provider schemas — so the azuread v3 attribute names (`azuread_application.client_id`, `azuread_service_principal.client_id`), `databricks_service_principal.application_id`, the `databricks_workspace_binding` fields, `isolation_mode`, and the `databricks_grants` block shape are all schema-confirmed, not just guessed.

### What didn't work

Nothing failed. Both `validate` runs were clean on the first try (`Success! The configuration is valid.`, no warnings). No plan/apply was run by design, so nothing surfaced at runtime.

### What I learned

azuread v3 uses `client_id` on both `azuread_application` (computed) and `azuread_service_principal` (argument) — the old `application_id` names are gone — while the Databricks side still calls it `application_id` on `databricks_service_principal`. So the same GUID crosses the provider boundary under two different attribute names in one `for_each` chain. Confirmed by a passing `validate`, not from memory.

### What was tricky

The apply-ordering coupling between the two roots is the sharp edge: `infra/` grants reference a principal that does not exist until `platform/` applies. I kept it explicit (output → `-var`) so the dependency is visible in the run recipe rather than buried in state. The other subtlety is that authoritative grants on ISOLATED catalogs need the account group/SP to be *resolvable in the workspace* — that is an apply-time identity-federation concern the module cannot enforce (see What warrants review).

### What warrants review

Everything here is offline-validated only; schema is correct but no apply was attempted. Real apply-time unknowns to check: (1) Entra app registration (`azuread_application`/`azuread_service_principal`) needs directory rights in the tenant. (2) `databricks_service_principal`/`databricks_group` on the account provider need the CLI principal to be a Databricks **account admin**. (3) The authoritative `databricks_grants` and `databricks_workspace_binding` run against the **already-deployed** catalogs — expected, but they will rewrite the full grant set and add the binding on live objects. (4) Likely follow-up: for the workspace-level grants to resolve, the account group and account SP must be **assigned to each workspace** (identity federation / permission assignment). The task scope stopped at account-level creation + registration; if apply errors with "principal not found", that assignment is the missing piece. Reviewer should also confirm `auth_type = "azure-cli"` is the intended account-provider auth.

### Future work

Apply order main must follow: (1) `platform/` init + apply → creates Entra apps/SPs, account groups, account SP registrations. (2) Read `terraform -chdir=platform output -json service_principal_application_ids`. (3) For each env in order (dev → test → prod): `infra/` init with `backend-<env>.hcl`, then apply with `-var-file=<env>.tfvars -var "service_principal_application_id=<platform output for that env>"`. Prod apply needs Benny's explicit approval per the standing rule. Possible follow-up: add workspace permission-assignment for the account group/SP if grants fail to resolve; and consider outputting the SP object IDs from `platform/` if Power BI/ADF wiring later needs them.
