import asyncio
from dataclasses import replace
from io import BytesIO

from fastapi import UploadFile
from fastapi.testclient import TestClient

from app.api.routes import connector_runs
from app.main import app
from app.services.data import CsvInputError, csv_bundle_from_uploads


def test_product_brief_states_human_approval_boundary() -> None:
    response = TestClient(app).get("/product/brief")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "local_public_benchmark_runtime"
    assert "autonomous purchasing" in payload["non_goals"]
    assert len(payload["how"]) == 10


def test_csv_connector_endpoint_is_disabled_without_authorised_server_configuration() -> None:
    response = TestClient(app).post(
        "/v1/connector-runs/csv",
        data={"tenant_id": "tenant-a", "authorization_reference": "pilot-record"},
        files={
            "products": ("products.csv", "product_id,sku,name,quantity_unit\np-1,s-1,Item,each\n"),
            "locations": ("locations.csv", "location_id,name,type\nl-1,Main,store\n"),
            "order_lines": ("orders.csv", "order_id,sku,location_id,occurred_at,quantity,status\no-1,s-1,l-1,2026-01-01T00:00:00+00:00,1,completed\n"),
            "inventory_snapshots": ("inventory.csv", "snapshot_at,sku,location_id,on_hand\n2026-01-01T00:00:00+00:00,s-1,l-1,1\n"),
        },
    )

    assert response.status_code == 503


def test_csv_connector_remains_disabled_when_only_the_legacy_enable_flag_is_true(monkeypatch) -> None:
    monkeypatch.setattr(
        connector_runs,
        "settings",
        replace(connector_runs.settings, csv_ingestion_enabled=True),
    )

    response = TestClient(app).post(
        "/v1/connector-runs/csv",
        data={"tenant_id": "tenant-a", "authorization_reference": "pilot-record"},
        files={
            "products": ("products.csv", "product_id,sku,name,quantity_unit\np-1,s-1,Item,each\n"),
            "locations": ("locations.csv", "location_id,name,type\nl-1,Main,store\n"),
            "order_lines": ("orders.csv", "order_id,sku,location_id,occurred_at,quantity,status\no-1,s-1,l-1,2026-01-01T00:00:00+00:00,1,completed\n"),
            "inventory_snapshots": ("inventory.csv", "snapshot_at,sku,location_id,on_hand\n2026-01-01T00:00:00+00:00,s-1,l-1,1\n"),
        },
    )

    assert response.status_code == 503
    assert "hard-disabled" in response.json()["detail"]


def test_application_composes_only_the_documented_public_routes() -> None:
    documented_paths = {
        "/health",
        "/product/brief",
        "/system/blueprint",
        "/v1/connector-runs/csv",
        "/v1/runs/{run_id}",
    }

    assert documented_paths.issubset(app.openapi()["paths"])


def test_csv_upload_reader_rejects_oversized_input_without_accepting_a_bundle() -> None:
    upload = UploadFile(filename="products.csv", file=BytesIO(b"x" * 9))

    try:
        asyncio.run(csv_bundle_from_uploads({"products": upload}, max_upload_bytes=8))
    except CsvInputError as error:
        assert "exceeds" in str(error)
    else:
        raise AssertionError("Oversized CSV input must be rejected")
