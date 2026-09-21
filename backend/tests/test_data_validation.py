"""Tests for the deterministic authorised CSV connector contract."""

from datetime import datetime, timezone

from app.schemas.connector import ConnectorRunRequest
from app.services.validation import CsvBundle, CsvConnectorValidator


AS_OF = datetime(2026, 9, 14, 3, 0, tzinfo=timezone.utc)


def canonical_bundle(**overrides: str) -> CsvBundle:
    tables = {
        "products": "product_id,sku,name,quantity_unit\np-1,sku-1,Coffee,each\n",
        "locations": "location_id,name,type\nstore-1,Main Store,store\n",
        "order_lines": (
            "order_id,sku,location_id,occurred_at,quantity,status\n"
            "o-1,sku-1,store-1,2026-09-13T09:00:00+00:00,2,completed\n"
            "o-2,sku-1,store-1,2026-09-13T10:00:00+00:00,1,fulfilled\n"
        ),
        "inventory_snapshots": (
            "snapshot_at,sku,location_id,on_hand\n"
            "2026-09-14T02:30:00+00:00,sku-1,store-1,20\n"
        ),
        "inbound_supply": (
            "supply_id,sku,location_id,expected_at,quantity,status\n"
            "s-1,sku-1,store-1,2026-09-17T09:00:00+00:00,10,confirmed\n"
        ),
        "supplier_terms": "supplier_id,sku,lead_time_days\nsupplier-1,sku-1,3\n",
    }
    tables.update(overrides)
    return CsvBundle.from_text(tables)


def request(**overrides: object) -> ConnectorRunRequest:
    values: dict[str, object] = {
        "tenant_id": "tenant-demo",
        "authorization_reference": "pilot-agreement-2026-09",
        "as_of": AS_OF,
    }
    values.update(overrides)
    return ConnectorRunRequest(**values)


def test_valid_complete_bundle_passes_all_connector_uses() -> None:
    outcome = CsvConnectorValidator().validate(request(), canonical_bundle())

    assert outcome.result.status == "PASS"
    assert outcome.result.approved_uses == (
        "demand_forecast",
        "inventory_risk",
        "replenishment_draft",
    )
    assert outcome.manifest.row_counts["order_lines"] == 2
    assert len(outcome.manifest.source_hash) == 64
    assert outcome.manifest.issues == ()


def test_unknown_sku_rejects_the_bundle() -> None:
    bundle = canonical_bundle(
        order_lines=(
            "order_id,sku,location_id,occurred_at,quantity,status\n"
            "o-1,unknown-sku,store-1,2026-09-13T09:00:00+00:00,2,completed\n"
        )
    )
    outcome = CsvConnectorValidator().validate(request(), bundle)

    assert outcome.result.status == "REJECT"
    assert "UNKNOWN_SKU" in outcome.result.limitations
    assert outcome.result.approved_uses == ()


def test_stale_inventory_limits_risk_and_replenishment() -> None:
    bundle = canonical_bundle(
        inventory_snapshots=(
            "snapshot_at,sku,location_id,on_hand\n"
            "2026-09-10T02:30:00+00:00,sku-1,store-1,20\n"
        )
    )
    outcome = CsvConnectorValidator().validate(request(max_inventory_age_hours=24), bundle)

    assert outcome.result.status == "PASS_WITH_LIMITATIONS"
    assert outcome.result.approved_uses == ("demand_forecast",)
    assert set(outcome.result.blocked_uses) == {"inventory_risk", "replenishment_draft"}
    assert "STALE_INVENTORY" in outcome.result.limitations


def test_missing_authorisation_reference_is_rejected_before_a_run() -> None:
    try:
        request(authorization_reference=" ")
    except ValueError as error:
        assert "authorization_reference" in str(error)
    else:
        raise AssertionError("An empty authorisation reference must be rejected")


def test_malformed_csv_row_rejects_the_bundle() -> None:
    outcome = CsvConnectorValidator().validate(
        request(),
        canonical_bundle(
            locations="location_id,name,type\nstore-1,Main Store,store,unexpected\n"
        ),
    )

    assert outcome.result.status == "REJECT"
    assert "MALFORMED_ROW" in outcome.result.limitations
