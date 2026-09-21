# RetailOps ML Lifecycle Audit

Before a release or pilot, verify:

- every connector is authorised, read-only by default, tenant-scoped, and
  versioned;
- raw snapshots, mappings, features, model configurations, metrics, and agent
  decisions are reproducible;
- time splits and feature generation do not leak future data;
- the baseline is retained when no candidate meets promotion criteria;
- inventory and lead-time evidence is current enough for the proposed use;
- Policy Critic blocks unsupported recommendations and autonomous actions;
- demo, synthetic, and public benchmark data cannot be presented as customer
  results;
- reviewer decisions, overrides, monitoring, retraining, and rollback events
  are auditable;
- no customer credentials or personal data are exposed to browser or logs.

## Current local assessment

This assessment covers only the implemented local connector, public benchmark,
baseline/fixed-candidate lifecycle, one immutable final-test report, Stage 5
specialist contracts, synchronous fixture-only workflow and reviewer queue,
pilot-readiness preparation, and P0 foundation-contract preparation. It is not
a production or pilot approval.

| Audit area | Local result | Evidence |
| --- | --- | --- |
| Connector boundary | PASS for fixture behavior | The CSV endpoint is disabled by default; tests cover malformed, oversized, duplicate, unknown-SKU, stale, and unauthorised inputs. |
| Pilot readiness | PASS for fixture behavior | Tests prove non-secret pilot metadata is immutable, write/non-CSV access is rejected, missing authorisation/header evidence is inconclusive, and a complete local declaration still cannot authorise customer-data ingestion. |
| P0 foundation contract | PASS for fixture behavior | Non-secret identity, secret-store, audit-store, object-store, worker, scheduler, and role-boundary references are immutably assessed. Missing declarations are `INCONCLUSIVE`; activation and ingestion are `REJECT`. A local SQLite migration adapter proves tenant-partitioned fixture audit records plus atomic blocked job/schedule events; fixture scope validation cannot authenticate a user and worker/scheduler dispatch remains disabled. |
| Snapshot and decision traceability | PASS for fixture behavior | Immutable snapshot manifests, source/schema hashes, run events, and typed Data Contract decisions are persisted by the local-pilot adapter. |
| Baseline chronology | PASS for fixture behavior | Tests prove validation-only MAE/RMSE, a locked unevaluated final test period, insufficient-history `INCONCLUSIVE`, and future-observation `REJECT`. |
| Fixed-candidate lifecycle | PASS for fixture behavior | Tests prove a predeclared candidate is compared only against the matching accepted baseline/snapshot, strictly promotes only on validation improvement, retains the baseline on a tie, records configuration/metrics/selection/rollback in a non-overwriting local registry artifact, and does not let locked final-test values affect validation metrics. |
| Public benchmark boundary | PASS for local adapter behavior | FreshRetailNet tests require an explicit 20–50 store-product selection across one to three stores, validate schema/continuous daily coverage, preserve zero sales, persist immutable public provenance, and attach limitations that block inventory, replenishment, production scoring, and customer claims. No source data is bundled or automatically downloaded. |
| Public final-test report | PASS_WITH_LIMITATIONS for the recorded public run | Immutable report `final-test-a4c2a81f-92f4-4e65-a3fa-289d033f796c` verifies table hashes, feature hash, scope splits, and registry chain before evaluating the validation-selected retained baseline once. It records macro MAE 0.6368571429 and RMSE 0.8062199696 for 20 seven-day scopes, retains public-data limitations, and cannot change selection. |
| Stage 5 specialist contracts | PASS for fixture behavior | Inventory Risk, Impact Ranking, Policy Critic, and Action Drafting have typed deterministic fixtures. Missing inventory, lead time, inbound coverage, or eligible upstream evidence returns `INCONCLUSIVE`; public benchmark inputs cannot create an action path; external operations are rejected; fixture drafts are review-only and non-executable. |
| Fixture specialist workflow | PASS for fixture behavior | A synchronous fixture-only orchestrator persists only named local transitions with evidence references. It creates a queue case only after a critic-approved draft; missing lead time ends `INCONCLUSIVE`, non-fixture input ends `REJECTED`, and no terminal path creates a review case. |
| Fixture reviewer queue | PASS for fixture behavior | Critic-approved fixture drafts enter immutable local case storage. Planner-role decisions append `DEFER`, `APPROVE`, or `DECLINE` events; terminal decisions cannot be overwritten and approval has no external execution effect. Public and retailer classifications are rejected by this local queue. |
| Customer-data / production controls | NOT ASSESSED | No authorised retailer source, tenant authentication, provisioned durable production storage, queue, scheduler, or monitoring deployment exists. The local P0 contract is not an external control implementation. |
| Production promotion, review, and action controls | NOT ASSESSED | No authorised evaluation, production registry, human-reviewed release decision, production specialist worker, authenticated reviewer workflow, or external action capability exists. The local workflow and queue are fixture-only. |

Do not treat the local PASS entries as retail performance, a trained model, or
permission to enable the connector. An authorised deployment and a complete
pilot audit are required before that claim.
