"""RetailOps ML API foundation and first server-side connector gate."""

from datetime import datetime
from typing import Annotated

from fastapi import FastAPI, File, Form, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.schemas.connector import ConnectorRunRequest
from app.services.data import CsvInputError, csv_bundle_from_uploads
from app.services.orchestrator import CsvConnectorRunner
from app.services.storage import SnapshotStore
from app.system_blueprint import build_system_blueprint


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Evidence-first retail demand and inventory decision support.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/health", tags=["system"])
def health_check() -> dict[str, str]:
    return {"status": "ok", "service": settings.app_name, "version": settings.app_version}


@app.get("/product/brief", tags=["product"])
def product_brief() -> dict[str, object]:
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


@app.get("/system/blueprint", tags=["system"])
def system_blueprint() -> dict[str, object]:
    """Expose the inspectable architecture without claiming a live workload."""

    return build_system_blueprint()


def _parse_as_of(value: str | None) -> datetime | None:
    if value is None or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise HTTPException(status_code=422, detail="as_of must be ISO-8601 with timezone") from error
    if parsed.tzinfo is None:
        raise HTTPException(status_code=422, detail="as_of must include a timezone")
    return parsed


def _require_csv_ingestion_enabled() -> None:
    if not (
        settings.csv_ingestion_enabled
        and settings.authenticated_tenant_runtime_implemented
    ):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "CSV ingestion is hard-disabled until an authenticated tenant runtime, "
                "durable production foundations, and authorised server deployment are implemented."
            ),
        )


@app.post("/v1/connector-runs/csv", status_code=status.HTTP_201_CREATED, tags=["connector"])
async def create_csv_connector_run(
    tenant_id: Annotated[str, Form(min_length=1)],
    authorization_reference: Annotated[str, Form(min_length=1)],
    products: Annotated[UploadFile, File()],
    locations: Annotated[UploadFile, File()],
    order_lines: Annotated[UploadFile, File()],
    inventory_snapshots: Annotated[UploadFile, File()],
    inbound_supply: Annotated[UploadFile | None, File()] = None,
    supplier_terms: Annotated[UploadFile | None, File()] = None,
    source_name: Annotated[str, Form()] = "authorised_csv_export",
    mapping_version: Annotated[str, Form()] = "csv-v1",
    as_of: Annotated[str | None, Form()] = None,
    max_inventory_age_hours: Annotated[int, Form(ge=1, le=720)] = 24,
) -> dict[str, object]:
    """Create an immutable, read-only connector run from authorised CSV exports.

    The endpoint is disabled by default. It must sit behind authenticated,
    tenant-scoped server access before it receives a customer's operational data.
    """

    _require_csv_ingestion_enabled()
    try:
        bundle = await csv_bundle_from_uploads(
            {
                "products": products,
                "locations": locations,
                "order_lines": order_lines,
                "inventory_snapshots": inventory_snapshots,
                "inbound_supply": inbound_supply,
                "supplier_terms": supplier_terms,
            },
            max_upload_bytes=settings.max_csv_upload_bytes,
        )
        request = ConnectorRunRequest(
            tenant_id=tenant_id,
            authorization_reference=authorization_reference,
            source_name=source_name,
            mapping_version=mapping_version,
            as_of=_parse_as_of(as_of),
            max_inventory_age_hours=max_inventory_age_hours,
        )
    except (CsvInputError, ValueError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    run = CsvConnectorRunner.for_root(settings.audit_root).run(request, bundle)
    return run.to_dict()


@app.get("/v1/runs/{run_id}", tags=["connector"])
def get_connector_run(run_id: str) -> dict[str, object]:
    """Return a persisted connector-run summary without raw source rows."""

    _require_csv_ingestion_enabled()
    payload = SnapshotStore(settings.audit_root).load_run(run_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="Connector run not found")
    return payload
