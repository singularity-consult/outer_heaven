# Azure landing zone design areas

The shared foundation under both analytics tracks. CAF defines eight design areas, split into **environment** (the platform foundation, decided early and expensive to change) and **compliance** (security/governance/management, refined iteratively).

When reviewing a platform, walk each area and ask three things: *Has this decision been made? Is it deliberate? Does the deployed reality match the stated design?* A design area that was never consciously decided is the most common source of expensive rework.

## Environment design areas (foundation — decide early)

### A. Azure billing and Microsoft Entra tenant
Tenant, enrollment, billing setup. The boundary everything else lives in.
- Review for: correct tenant (a recurring real trap — e.g. a private project landing in a customer's tenant by accident), billing scope, EA/MCA enrollment.

### B. Identity and access management
The primary security boundary in the cloud. Foundation for any compliant architecture.
- Review for: human identities vs service principals/managed identities; who deploys (CI service principal vs personal login); RBAC scoping; whether data-plane access (Unity Catalog grants, Purview policies) is modelled deliberately, not ad hoc.

### C. Resource organisation
Management group hierarchy and subscription design. Drives governance, operations, and scaling.
- Review for: subscription boundaries (data management vs data landing zones get their own subscriptions in cloud-scale analytics — see the Databricks reference); management group placement; resource-group granularity; naming and tagging consistency.

### E. Network topology and connectivity
Hub-spoke vs Virtual WAN; private connectivity. Foundational and hard to retrofit.
- Review for: VNet injection model for Databricks (public/private/host subnets, NSGs); private endpoints vs public access on storage and key vault; peering to a connectivity hub; DNS. Networking shortcuts taken early are among the most painful to undo.

## Compliance design areas (refine iteratively)

### F. Security
Controls and processes protecting the estate.
- Review for: data encryption (at rest/in transit), key management (Key Vault, CMK), secret hygiene (no secrets in state/code — see the `terraform` skill), Defender for Cloud coverage, network isolation of data planes.

### D/G/H. Management
The operations baseline: visibility, monitoring, protect-and-recover.
- Review for: diagnostic/log routing (Log Analytics), monitoring and alerting on pipelines, backup/recovery posture, cost monitoring.

### Governance
Automated auditing and enforcement of policy.
- Review for: Azure Policy assignments (e.g. enforce private endpoints, allowed regions, required tags), data governance tooling (Purview registration/classification, Unity Catalog), drift between policy intent and reality.

### I. Platform automation and DevOps
The tools and templates that deploy landing zones and workloads.
- Review for: IaC coverage (is everything in Terraform, or is there click-ops drift?), CI/CD with a deployment service principal (the target state — see how DataEstate2026 deploys via GitHub Actions), environment promotion (dev/test/prod), state hygiene.

## Using this for a review

The design areas are a sequence, not a scorecard. Go in order; where an area is already handled well, note it and move on. The output that matters is: *which design decisions were never actually made, and which of those will be expensive to fix once data and workloads are on the platform.*

A caution for small/learning contexts (like datavilla): the landing-zone model is enterprise-scaled. A single-subscription learning project does not need a separate data management landing zone or a connectivity hub. Apply the *thinking* (have I decided identity, network, governance deliberately?) without forcing the *enterprise topology*. Over-applying CAF is a real failure mode, not diligence.
