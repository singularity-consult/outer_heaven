# Unify data platform — Microsoft Fabric / OneLake

The 2026 CAF analytics guidance, centred on Microsoft Fabric. Where cloud-scale analytics (the Databricks track) builds the platform from Azure primitives, the Fabric track delivers much of it as a managed SaaS data platform. Microsoft is steering its analytics guidance toward this track, so expect the docs Benny references to keep shifting here.

Use this track when the solution is Fabric-based, or when advising a greenfield, Microsoft-centric customer. For Databricks-invested customers (SEGES), the other track still holds.

## The four-step framework

Microsoft frames unifying a data platform as four steps — useful as a review spine even outside Fabric:

1. **Organizational readiness** — define the data strategy; establish data ownership and **data domains**; clarify how data creates business value and who is accountable for which data. (People and ownership before tech.)
2. **Architecture** — stand up Fabric and the required Azure environments. OneLake as the single logical lake; Fabric capacities as compute.
3. **Governance and security baselines** — **Microsoft Purview** for central visibility and governance across the estate; bake security/compliance baselines into the Fabric architecture from the start, not bolted on.
4. **Operational standards** — consistent processes for ingesting raw data, building data products, and managing their lifecycle: how products are published, secured, and consumed.

Review for: did they start at step 1 (ownership/domains) or jump straight to provisioning Fabric capacities and figure out ownership later? Skipping step 1 is the classic failure — a technically clean platform no one is accountable for.

## Key Fabric concepts

- **OneLake** — one logical data lake for the whole tenant. Data stored once, reused across engineering, warehousing, real-time, data science, and Power BI. Contrast with the Databricks track's explicit per-layer ADLS containers.
- **Shortcuts (virtualization)** — reference data where it already lives (ADLS, S3, other Fabric) without copying. Unify access without migration.
- **Mirroring (replication)** — selective replication of operational databases into OneLake. The copy-when-you-must counterpart to shortcuts.
- **Fabric capacities** — the compute/billing unit. The main cost lever alongside OneLake storage and Mirroring volume.
- **Power BI** — native to Fabric; licensing is either sufficient Fabric capacity or separate Power BI licenses. A real budgeting gotcha.
- **Fabric IQ / Foundry IQ** — the AI-context layer: letting Foundry agents reason over governed, trusted data. Relevant as Benny moves into AI engineering.

## Governance

Purview is the governance plane here too — centralised catalog, classification, and policy across OneLake, Azure, on-prem, SaaS, other clouds. In Fabric it is more native than in the Databricks track (governance defined once, applied across the platform rather than recreated per tool).

Review for: governance defined once and inherited, vs policies recreated per workspace; Purview actually spanning the estate vs only cataloguing Fabric.

## Review checklist (track-specific)

- Started at ownership/domains (step 1), or provisioned tech first?
- OneLake used as the single lake, or fragmented into silos that defeat the point?
- Shortcuts vs Mirroring chosen deliberately (virtualize by default, replicate only when required)?
- Fabric capacity sizing and Power BI licensing budgeted (not discovered later)?
- Purview spanning the whole estate, or only Fabric?
- Security/compliance baselines built in from step 3, or deferred?

## When advising between the tracks

Greenfield + Microsoft-centric + wants fast time-to-value with minimal migration → Fabric. Heavy existing Databricks/Spark investment, multi-cloud, or fine-grained control needs → cloud-scale analytics (Databricks track). The honest answer to a customer is usually "it depends on what you already run" — don't let Microsoft's current Fabric push override an existing Databricks estate that works.
