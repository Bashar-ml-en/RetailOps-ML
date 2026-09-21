"""Non-sensitive system and product-discovery endpoints."""

from fastapi import APIRouter

from app.config import settings
from app.system_blueprint import build_system_blueprint


router = APIRouter()


@router.get("/health", tags=["system"])
def health_check() -> dict[str, str]:
    """Return a dependency-free liveness response."""

    return {"status": "ok", "service": settings.app_name, "version": settings.app_version}


@router.get("/product/brief", tags=["product"])
def product_brief() -> dict[str, object]:
    """Describe the implemented local boundary without claiming live operations."""

    return {
        "product": settings.app_name,
        "status": "local_lifecycle_gates",
        "why": "Help retail planners prioritise demand and inventory decisions from authorised operational data.",
        "what": "Implemented local pilot-readiness, P0 provisioning-foundation contracts with a SQLite fixture audit migration, FreshRetailNet public-benchmark, baseline/model lifecycle, one labelled final-test report, deterministic review-case contracts, and a persisted fixture-only reviewer queue; an authorised pilot and authenticated workflow remain absent.",
        "how": [
            "Record non-secret pilot scope and source-boundary evidence; block customer-data ingestion until authenticated tenant controls exist.",
            "Map only an explicit FreshRetailNet public-benchmark subset into an immutable, licence-attributed snapshot; block inventory, replenishment, production, and retailer claims.",
            "Assess non-secret P0 identity, secret-store, audit-store, object-store, worker, scheduler, and role-boundary references as provisioning-only contracts; SQLite persists only tenant-partitioned fixture metadata and blocked jobs, while runtime activation stays hard-blocked.",
            "Validate versioned connector snapshots with the implemented disabled CSV gate.",
            "Build a daily demand series and evaluate only the declared naïve baseline on chronological validation while the final test partition remains locked.",
            "Compare the single predeclared candidate with the baseline on validation only; retain the baseline on any tie or regression and record a local rollback reference.",
            "Evaluate the validation-selected public benchmark model once on the locked final test in a separate immutable report; never change selection from the result.",
            "Use deterministic specialist contracts in a synchronous fixture-only event workflow that returns INCONCLUSIVE for missing inventory, inbound, lead-time, identity, or policy evidence; the local queue records approve, decline, or defer audit events without external execution.",
        ],
        "impact_measurement": [
            "forecast error against a declared baseline",
            "qualified review cases",
            "planner response time",
            "stockout days and excess-inventory measures when available",
        ],
        "non_goals": [
            "autonomous purchasing",
            "inventory transfer",
            "price changes",
            "unmeasured business guarantees",
            "claiming a trained customer model without an authorised evaluation run",
        ],
    }


@router.get("/system/blueprint", tags=["system"])
def system_blueprint() -> dict[str, object]:
    """Expose the inspectable architecture without claiming a live workload."""

    return build_system_blueprint()
