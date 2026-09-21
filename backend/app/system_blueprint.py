"""Inspectable architecture metadata for the RetailOps control-room UI.

This module intentionally describes the target operating model; it does not
pretend that a connector, training job, model, or agent workload is live.
Keeping this boundary in the API lets the UI distinguish implemented controls
from components that must be built and validated in later stages.
"""

from typing import Any


def build_system_blueprint() -> dict[str, Any]:
    """Return the versioned system blueprint used by the architecture explorer."""

    return {
        "blueprint_version": "2026.09.p0_sqlite_fixture_audit",
        "mode": "ARCHITECTURE_BLUEPRINT",
        "live_workloads": "NONE",
        "truthful_status": {
            "implemented_now": [
                "product and lifecycle governance",
                "typed agent-decision contract",
                "health, product-brief, and blueprint API routes",
                "architecture explorer UI",
                "pilot-readiness assessment and immutable local audit artifact (local code only)",
                "P0 non-secret production-foundation provisioning contract with fixture tenant-role checks, SQLite audit migration, and blocked worker/scheduler records",
                "FreshRetailNet public-benchmark adapter and immutable limited snapshot (local code only)",
                "server-side CSV snapshot and Data Contract Agent (disabled by default)",
                "chronology-safe daily demand baseline evaluator and Forecast Evaluation Agent (local code only)",
                "fixed-candidate validation comparison and immutable local model-registry artifact (local code only)",
                "one immutable, labelled FreshRetailNet final-test report for the validation-selected local model",
                "deterministic Stage 5 Inventory Risk, Impact Ranking, Policy Critic, and Action Drafting contracts with fixture-only success and failure paths",
                "synchronous fixture-only workflow that persists actual specialist, terminal, and review-ready events",
                "fixture-only persisted reviewer queue with append-only approve, decline, and defer audit events",
            ],
            "not_running_yet": [
                "authorised retailer source and server configuration",
                "feature jobs",
                "authorised baseline or candidate-model evaluation",
                "asynchronous or parallel specialist worker",
                "authenticated reviewer queue and human identity controls",
                "production model registry, deployment, and drift monitoring",
            ],
        },
        "stages": [
            {
                "id": "pilot-readiness",
                "title": "Pilot readiness and source boundary",
                "state": "IMPLEMENTED",
                "owner": "Pilot governance",
                "output": "Non-secret readiness assessment; customer-data ingestion remains blocked",
            },
            {
                "id": "production-foundation",
                "title": "P0 production-foundation contract",
                "state": "CONTRACT_DEFINED",
                "owner": "Platform security",
                "output": "Non-secret resource declaration, fixture role-scope validation, tenant-partitioned SQLite fixture audit migration, and blocked job/schedule records; no infrastructure, customer API, or tenant authentication is live",
            },
            {
                "id": "public-benchmark",
                "title": "Public benchmark source mapping",
                "state": "IMPLEMENTED",
                "owner": "Benchmark data adapter",
                "output": "Versioned FreshRetailNet benchmark snapshot; inventory, replenishment, and customer claims blocked",
            },
            {
                "id": "connector",
                "title": "Authorised CSV connector",
                "state": "IMPLEMENTED",
                "owner": "Data platform",
                "output": "Immutable snapshot or validation failure; server disabled by default",
            },
            {
                "id": "validation",
                "title": "Data contract gate",
                "state": "IMPLEMENTED",
                "owner": "Data Contract Agent",
                "output": "Typed PASS, limitation, REJECT, or INCONCLUSIVE decision",
            },
            {
                "id": "features",
                "title": "Daily demand feature build",
                "state": "IMPLEMENTED",
                "owner": "ML platform",
                "output": "Versioned SKU-location-unit daily demand series for baseline evaluation",
            },
            {
                "id": "evaluation",
                "title": "Chronology-safe baseline evaluation",
                "state": "IMPLEMENTED",
                "owner": "Forecast Evaluation Agent",
                "output": "Validation MAE/RMSE; the selected FreshRetailNet local model has one separate, immutable public final-test report",
            },
            {
                "id": "model-lifecycle",
                "title": "Fixed-candidate lifecycle and local registry",
                "state": "IMPLEMENTED",
                "owner": "Forecast Evaluation Agent",
                "output": "Strict validation-only candidate selection or retained baseline, rollback reference, and no selection change from final-test reporting",
            },
            {
                "id": "review",
                "title": "Fixture decision review",
                "state": "IMPLEMENTED",
                "owner": "Specialist agent group",
                "output": "Synchronous fixture workflow persists actual specialist events, terminal safety outcomes, and critic-approved queue cases; worker and authenticated tenant workflow remain absent",
            },
            {
                "id": "human",
                "title": "Human approval",
                "state": "CONTRACT_DEFINED",
                "owner": "Retail planner",
                "output": "Fixture planner role can approve, decline, or defer a non-executable draft; authenticated human workflow remains absent",
            },
            {
                "id": "monitoring",
                "title": "Outcome and drift monitoring",
                "state": "PLANNED",
                "owner": "MLOps",
                "output": "Auditable alert, retrain, or rollback proposal",
            },
        ],
        "agents": [
            {
                "id": "data-contract",
                "name": "Data Contract Agent",
                "responsibility": "Checks identity, units, timestamps, coverage, and snapshot provenance.",
                "parallel_group": "evidence-review",
                "state": "IMPLEMENTED",
            },
            {
                "id": "forecast-evaluation",
                "name": "Forecast Evaluation Agent",
                "responsibility": "Compares the declared baseline and eligible candidates on chronological validation.",
                "parallel_group": "evidence-review",
                "state": "IMPLEMENTED",
            },
            {
                "id": "inventory-risk",
                "name": "Inventory Risk Agent",
                "responsibility": "Assesses the evidence needed to qualify a stockout or excess-inventory review case.",
                "parallel_group": "evidence-review",
                "state": "IMPLEMENTED",
            },
            {
                "id": "impact-ranking",
                "name": "Impact Ranking Agent",
                "responsibility": "Ranks eligible cases using declared operational evidence, never hidden reasoning.",
                "parallel_group": "evidence-review",
                "state": "IMPLEMENTED",
            },
            {
                "id": "policy-critic",
                "name": "Policy Critic",
                "responsibility": "Vetoes unsupported claims, incomplete evidence, unsafe drafts, and missing approval paths.",
                "parallel_group": "release-gate",
                "state": "IMPLEMENTED",
            },
            {
                "id": "action-drafting",
                "name": "Action Drafting Agent",
                "responsibility": "Creates an evidence-linked draft only after all gates pass; a human still decides.",
                "parallel_group": "release-gate",
                "state": "IMPLEMENTED",
            },
        ],
        "lifecycle": [
            "Record non-secret pilot readiness; require authenticated tenant controls before any customer-data ingestion.",
            "Assess the required identity, secret-store, audit-store, object-store, worker, scheduler, and role-boundary references as non-secret provisioning evidence; a local SQLite adapter records only tenant-partitioned fixture metadata and blocked jobs while activation stays hard-disabled.",
            "Map an explicit public benchmark subset with source licence and limitations; never treat it as a retailer tenant.",
            "Version connector snapshot and mappings.",
            "Build historical-only features per compatible SKU, location, and unit.",
            "Backtest the naïve baseline before the single fixed candidate using chronological splits.",
            "Lock the final test period; record validation metrics, configuration, local selection, and rollback baseline.",
            "After selection, permit one immutable, labelled public-benchmark final-test report that cannot change the selected model.",
            "Use deterministic Stage 5 specialist contracts in a synchronous fixture-only event workflow; fail closed on missing inventory, inbound, lead-time, identity, or policy evidence, and keep an authenticated workflow required.",
            "Persist only actual fixture workflow transitions with evidence references; terminal outcomes create no review case and no event permits external execution.",
            "Persist fixture-only reviewer queue decisions as immutable approve, decline, or defer events; approval never invokes an external action.",
            "Require an authorised evaluation and human-reviewed release before any production champion is deployed.",
            "Monitor realised error, coverage, schema/feature drift, freshness, and reviewer outcomes.",
            "Propose retraining or rollback through an auditable human-reviewed change request.",
        ],
        "controls": [
            {
                "title": "Public benchmark boundary",
                "detail": "FreshRetailNet benchmark snapshots preserve public-source provenance and can support only limited forecast evaluation, never customer claims or inventory/replenishment decisions.",
                "state": "ENFORCED_BY_POLICY",
            },
            {
                "title": "Pilot access readiness",
                "detail": "Reject write/non-CSV first-pilot boundaries and keep customer-data ingestion blocked until authenticated tenant controls exist.",
                "state": "PARTIAL",
            },
            {
                "title": "P0 production foundation contract",
                "detail": "Non-secret resource declarations, fixture role-scope validation, SQLite migration/partition tests, and blocked job/schedule records are tested locally; real infrastructure, identity verification, customer API, and execution are absent.",
                "state": "CONTRACT_DEFINED",
            },
            {
                "title": "CI checks",
                "detail": "Unit tests, contract checks, baseline/candidate chronology checks, registry checks, and frontend production build.",
                "state": "PARTIAL",
            },
            {
                "title": "CD release gate",
                "detail": "Package a versioned service only after quality, security, and model-promotion checks pass.",
                "state": "PLANNED",
            },
            {
                "title": "Data and model drift",
                "detail": "Detect schema changes, missing coverage, freshness loss, feature drift, and realised-error deterioration.",
                "state": "PLANNED",
            },
            {
                "title": "Human decision boundary",
                "detail": "No purchase, transfer, price, or supplier action is executed by the system.",
                "state": "ENFORCED_BY_POLICY",
            },
        ],
    }
