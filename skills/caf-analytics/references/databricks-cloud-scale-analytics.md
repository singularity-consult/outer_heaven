# Cloud-scale analytics (Databricks + ADLS + Unity Catalog)

The CAF analytics scenario formerly called Enterprise-Scale Analytics. It builds on Azure landing zones (see `landing-zone-design-areas.md`) and adds an analytics-specific topology. This is Benny's default track: datavilla and DataEstate2026 both live here.

## The two building blocks

Cloud-scale analytics splits the platform into two kinds of landing zone, each typically its own subscription:

### Data Management Landing Zone
One per platform. Governs the *whole* analytics estate — it is the control plane, not where workloads run.
- Holds central governance: **Microsoft Purview** (registers data sources, classifies, enforces policy, powers self-service discovery), shared networking (a hub that peers to the data landing zones and the connectivity subscription), shared private DNS.
- Review for: is governance centralised here, or scattered per-workload? Is Purview actually registering the data lakes, or is it bought-and-idle?

### Data Landing Zone
The **unit of scale**. One or many. Where data is retained and workloads run.
- Holds: ADLS Gen2 data lakes, Databricks workspaces (VNet-injected), processing and ML compute. New business domains or capacity needs are met by adding *another* data landing zone, not by inflating one.
- Review for: is the "unit of scale" boundary deliberate (per domain / per business unit), or did everything pile into one zone because splitting felt like work?

## Core design principles

- **Data mesh** — decentralised ownership. Data is owned by the domains that produce it, not by a central team that becomes a bottleneck.
- **Data domains** — the organisational boundary (e.g. finance, livestock, agronomy). Domains map to data landing zones / catalog boundaries.
- **Data products** — curated, documented, discoverable datasets a domain publishes for others to consume. The unit of value and of governance.
- **Polyglot persistence** — use the right store for the job (lake, warehouse, real-time), not one engine forced onto everything.
- **Self-service with governance** — lines of business get autonomy *because* Purview/Unity Catalog make access governed and auditable, not despite it.

## Governance: Unity Catalog + Purview

The two are complementary, not redundant:
- **Unity Catalog** — Databricks-native governance: metastore (one per region — a hard constraint, plan it), catalogs/schemas/tables, grants, lineage *within* Databricks. The data-plane access model.
- **Microsoft Purview** — estate-wide catalog across Databricks, ADLS, SQL, Power BI, on-prem. Discovery, classification, and policy *above* any single engine.

Review for: a metastore-per-region collision (a second platform in the same region cannot create a second metastore — it must share or import); catalogs that map to medallion layers vs to data domains (both are valid — which did they choose, and does it match the data-mesh intent?); grants modelled as code vs clicked in by hand.

## Medallion organisation

The layered lake (landing → raw → base → enriched → curated → integration, or the classic bronze/silver/gold) is how a data landing zone organises storage. Review for: are layers separate containers/catalogs with distinct access (raw locked down, curated broadly readable)? Is promotion between layers a deliberate, governed step or an ad-hoc copy?

## Review checklist (track-specific)

- Subscription split: data management vs data landing zone(s) deliberate, or collapsed into one?
- Data landing zone boundary maps to a real domain / scale need?
- Purview registering the lakes and actually used for discovery?
- Unity Catalog metastore region decided with the per-region constraint in mind?
- Catalog topology (layer-aligned vs domain-aligned) matches the data-mesh intent?
- Medallion layers have distinct, deliberate access control?
- Grants and policies as code, not click-ops?

For a small/learning solution, most of this collapses: one subscription, one data lake, one metastore, layer-aligned catalogs. That's fine — apply the *principles* (deliberate layers, governed access) without the enterprise topology.
