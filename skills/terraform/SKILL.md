---
name: terraform
description: Conventions and safety rules for Terraform / IaC in Benny's repos (Azure-based, for example DataEstate2026-iac and Datavilla). Use this whenever you read or write Terraform (.tf) or plan an infrastructure change. Covers formatting, version pinning, state and secret hygiene, and the plan-before-apply and prod-approval safety rules.
---

# terraform

Terraform changes real infrastructure. A careless apply can break an environment. This skill is the standing conventions and, above all, the safety rules.

## Safety (the rules that matter most)

- **Plan before apply, always.** Run `terraform plan` and read it before any `apply`. Never apply blind.
- **Never apply to production without Benny's explicit approval** for that specific change. Show the plan first.
- **Never commit secrets or state.** No credentials, keys, or connection strings in `.tf`. No `terraform.tfstate` / `*.tfstate.backup` in git: state holds secrets in plaintext. State lives in the remote backend.
- **Call out destructive changes** (`-/+ replace`, `destroy`) explicitly before proceeding.

## Conventions

- **Run `terraform fmt`** so formatting is canonical, and **`terraform validate`** before committing.
- **Pin versions:** pin `required_version` and each provider in `required_providers`. Unpinned providers drift.
- **Remote state**, not local (Azure backend for the SEGES / DataEstate work).
- **Declare and describe** every `variable` (with `type` and `description`) and every `output` (with `description`).
- **No hardcoded environment values** in resources; use variables and per-environment `.tfvars`.
- **Module structure:** standard files (`main.tf`, `variables.tf`, `outputs.tf`, `versions.tf`); keep modules focused.

## Note

Benny's repo-specific conventions (module layout, naming, backend keys) refine this skill over time. When you see a convention in his existing `.tf` that this skill does not capture, follow the repo and flag it for adding here.
