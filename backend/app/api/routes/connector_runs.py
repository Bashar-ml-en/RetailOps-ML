"""Authorised connector-run endpoints.

The routes remain deliberately unavailable until an authenticated, tenant-scoped
runtime exists. Their separation makes that future boundary explicit without
turning an environment flag into an authorisation mechanism.
"""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from app.config import settings
from app.schemas.connector import ConnectorRunRequest
from app.services.data import CsvInputError, csv_bundle_from_uploads
from app.services.orchestrator import CsvConnectorRunner
from app.services.storage import SnapshotStore


router = APIRouter()


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


@router.post("/v1/connector-runs/csv", status_code=status.HTTP_201_CREATED, tags=["connector"])
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


@router.get("/v1/runs/{run_id}", tags=["connector"])
def get_connector_run(run_id: str) -> dict[str, object]:
    """Return a persisted connector-run summary without raw source rows."""

    _require_csv_ingestion_enabled()
    payload = SnapshotStore(settings.audit_root).load_run(run_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="Connector run not found")
    return payload
