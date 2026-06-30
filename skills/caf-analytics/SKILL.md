---
name: caf-analytics
description: A design-and-review lens for Azure analytics/data solutions, anchored in Microsoft's Cloud Adoption Framework (CAF) and Azure landing zones. Use this whenever Benny architects, reviews, or extends an Azure data platform — landing zone topology, subscription/resource organisation, networking, identity, governance (Purview/Unity Catalog), or the medallion/data-product layout — and whenever a solution should be held up against CAF best practice to find gaps. Covers both the Databricks + ADLS + Unity Catalog track (cloud-scale analytics) and the Microsoft Fabric / OneLake track. Trigger it even when CAF is not named explicitly but the work is clearly "is this analytics platform set up the right way".
---

# caf-analytics

This skill is a **lens, not an encyclopedia**. Its job is to take a real analytics solution Benny is designing or reviewing and hold it up against the Cloud Adoption Framework — so the gaps, the skipped design decisions, and the "we'll fix that later" shortcuts become visible while they are still cheap to fix.

Benny builds data platforms for a living (datavilla, DataEstate2026, customer work). He does not need CAF recited at him. He needs the framework used as a checklist that catches the thing he forgot, and as a vocabulary that makes a design defensible to a customer architect.

## When to use it

- Designing a new analytics solution or a new piece of one (a landing zone, a catalog layout, a networking topology, a governance setup).
- Reviewing an existing solution — Benny's own or a customer's — for "is this structured the way CAF would want, and if not, is the deviation deliberate or an oversight?"
- Deciding subscription / management-group / resource-group boundaries for a data platform.
- Whenever Benny is about to commit to an architecture decision that is expensive to reverse (subscription topology, metastore region, network injection model).

## How to run the review

The value is in the **gap-finding**, not in producing a tidy summary. Work like this:

1. **Establish the actual solution first.** Read the repo, the Terraform, the existing resources. Do not review against an imagined design. If you cannot see something (what's deployed, who owns governance), say so and ask rather than assume.
2. **Pick the track.** Databricks + ADLS + Unity Catalog, or Fabric / OneLake. They share the landing-zone foundation but differ sharply above it. See the track selection below.
3. **Walk the landing-zone design areas** (`references/landing-zone-design-areas.md`) — these are the foundation under *both* tracks. For each area, ask: has this decision been made, is it deliberate, and does it match what's actually deployed?
4. **Walk the track-specific design** (the relevant reference file). This is where the analytics-specific gaps live: data lake organisation, catalog/domain boundaries, governance tooling, self-service model.
5. **Report deviations, ranked by cost-to-fix.** A wrong subscription topology or metastore region is expensive to undo later and belongs at the top. A missing tag belongs at the bottom. For each gap, state whether it looks deliberate or accidental — don't assume an oversight.
6. **Challenge, don't rubber-stamp.** If the design is fine, say so plainly and move on. If a CAF "best practice" doesn't fit Benny's context (small project, single subscription, learning environment like datavilla), say that too — CAF is enterprise-scaled by default and over-applying it is its own failure mode.

## The CAF methodologies (the frame)

Seven methodologies. The first four are sequential (set up), the last three are continuous (operate):

- **Strategy** — why the org is adopting cloud; business outcomes. Rarely Benny's job, but it sets the constraints everything else lives within.
- **Plan** — turn strategy into a roadmap; assess the digital estate.
- **Ready** — the technical foundation: **Azure landing zones**. This is where most of Benny's architecture review lands.
- **Adopt** — deploy the workloads (the actual data pipelines, models, reports).
- **Govern** — ongoing policy adherence (Azure Policy, cost, Purview).
- **Secure** — securing the estate (identity, network, data protection).
- **Manage** — operations, monitoring, reliability.

For an analytics-platform review, **Ready (landing zones)** and the analytics scenario layered on top are the centre of gravity. Govern/Secure/Manage are the lenses you re-check as the platform grows.

## Track selection

Both tracks sit on the same Azure landing-zone foundation. Above that they diverge:

| | Databricks + ADLS + Unity Catalog | Microsoft Fabric / OneLake |
|---|---|---|
| CAF scenario | Cloud-scale analytics (former Enterprise-Scale Analytics) | Unify data platform for AI & analytics (2026) |
| Storage | ADLS Gen2, explicit containers per layer | OneLake, single logical lake |
| Compute | Databricks workspaces (VNet-injected) | Fabric capacities |
| Governance | Unity Catalog + Microsoft Purview | Microsoft Purview (native to Fabric) |
| Integration | Build it (peering, private endpoints) | Shortcuts (virtualization), Mirroring (replication) |
| Reference | `references/databricks-cloud-scale-analytics.md` | `references/fabric-onelake.md` |

**Which one:** match the track to what's actually being built. Benny's current work (datavilla, DataEstate2026) is the Databricks track — that's the default unless the solution is Fabric-based. Note for advising customers: Microsoft is actively steering cloud-scale analytics content toward the Fabric "unify data platform" framework, so the two tracks are converging in the docs. When a customer is greenfield and Microsoft-centric, Fabric is now Microsoft's default recommendation; when they are Databricks-invested (like SEGES), the cloud-scale analytics track still holds.

## References

- `references/landing-zone-design-areas.md` — the eight Azure landing-zone design areas. The shared foundation; walk these for any analytics platform review.
- `references/databricks-cloud-scale-analytics.md` — Data Management vs Data Landing Zones, data mesh / data products / data domains, Unity Catalog + Purview governance, medallion organisation.
- `references/fabric-onelake.md` — the four-step unify-data-platform framework, OneLake, shortcuts/mirroring, Fabric + Purview governance.

These mirror Microsoft Learn; when Microsoft's terminology shifts (it is, fast, around Fabric), trust the live docs over this skill and flag the drift so it can be updated here.
