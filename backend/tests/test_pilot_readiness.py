"""Fixture tests for the fail-closed authorised-pilot readiness gate."""

from dataclasses import replace
from datetime import date, datetime, timezone

from app.schemas.pilot import PilotReadinessRequest
from app.services.pilot_readiness import PILOT_READINESS_SCHEMA_VERSION, PilotReadinessRunner
from app.services.storage import SnapshotStore


def request(**overrides: object) -> PilotReadinessRequest:
    values: dict[str, object] = {
        "pilot_id": "pilot-fixture-001",
        "tenant_id": "fixture-tenant",
        "planner_owner_role": "demand_planner",
        "data_owner_role": "retail_data_owner",
        "security_approver_role": "security_approver",
        "authorization_reference": "approval-fixture-001",
        "authorization_attested": True,
        "source_mode": "CSV",
        "requested_access": "READ_ONLY",
        "transfer_channel": "approved_secure_transfer",
        "retention_rule": "fixture-only retention policy",
        "category": "repeat_purchase_fixture_category",
        "sku_scope": tuple(f"sku-{index}" for index in range(20)),
        "location_scope": ("store-1",),
        "operating_timezone": "UTC",
        "forecast_horizon_days": 7,
        "review_cadence": "WEEKLY",
        "current_planning_baseline": "planner_last_observation",
        "historical_period_start": date(2025, 1, 1),
        "historical_period_end": date(2025, 12, 31),
        "header_sample_reference": "deidentified-header-fixture-v1",
        "available_exports": (
            "products",
            "locations",
            "order_lines",
            "inventory_snapshots",
        ),
    }
    values.update(overrides)
    return PilotReadinessRequest(**values)


def runner() -> PilotReadinessRunner:
    return PilotReadinessRunner(clock=lambda: datetime(2026, 9, 16, tzinfo=timezone.utc))


def test_complete_metadata_is_audited_but_cannot_authorise_customer_data_ingestion(tmp_path) -> None:
    assessment = runner().assess(request())

    assert assessment.status == "PASS_WITH_LIMITATIONS"
    assert assessment.approved_uses == ("pilot_source_mapping",)
    assert "customer_data_ingestion" in assessment.blocked_uses
    assert assessment.next_action == "configure_authenticated_tenant_scope"
    assert assessment.to_dict()["authorization_state"] == "DECLARED_NOT_EXTERNALLY_VERIFIED"
    assert assessment.to_dict()["customer_data_ingestion_permitted"] is False

    store = SnapshotStore(tmp_path)
    store.persist_pilot_readiness(assessment)
    persisted = store.load_pilot_readiness(assessment.readiness_id)
    assert persisted is not None
    assert persisted["readiness_schema_version"] == PILOT_READINESS_SCHEMA_VERSION
    assert persisted["blocked_uses"] == list(assessment.blocked_uses)


def test_missing_authorisation_and_header_evidence_is_inconclusive() -> None:
    assessment = runner().assess(
        request(
            authorization_reference="",
            authorization_attested=False,
            header_sample_reference="",
            available_exports=("products", "locations"),
        )
    )

    assert assessment.status == "INCONCLUSIVE"
    assert assessment.approved_uses == ()
    assert "MISSING_AUTHORIZATION_REFERENCE" in assessment.limitations
    assert "AUTHORIZATION_NOT_ATTESTED" in assessment.limitations
    assert "MISSING_HEADER_SAMPLE_REFERENCE" in assessment.limitations
    assert "MISSING_REQUIRED_CSV_EXPORT_DECLARATION" in assessment.limitations


def test_write_access_or_a_non_csv_source_is_rejected() -> None:
    assessment = runner().assess(request(source_mode="Shopify", requested_access="WRITE"))

    assert assessment.status == "REJECT"
    assert assessment.approved_uses == ()
    assert assessment.limitations == (
        "FIRST_PILOT_REQUIRES_READ_ONLY_CSV",
        "REQUESTED_ACCESS_NOT_READ_ONLY",
    )
    assert assessment.next_action == "correct_access_boundary"


def test_cohort_outside_the_declared_first_pilot_scope_does_not_advance() -> None:
    assessment = runner().assess(request(sku_scope=("sku-1",), location_scope=()))

    assert assessment.status == "INCONCLUSIVE"
    assert assessment.approved_uses == ()
    assert assessment.limitations == (
        "SKU_SCOPE_OUTSIDE_DECLARED_PILOT_TARGET",
        "LOCATION_SCOPE_OUTSIDE_DECLARED_PILOT_TARGET",
    )


def test_duplicate_scope_ids_cannot_masquerade_as_a_complete_cohort() -> None:
    assessment = runner().assess(
        request(
            sku_scope=("sku-duplicate",) * 20,
            location_scope=("store-1", "store-1"),
        )
    )

    assert assessment.status == "INCONCLUSIVE"
    assert assessment.approved_uses == ()
    assert assessment.limitations == (
        "DUPLICATE_SKU_SCOPE_ENTRY",
        "DUPLICATE_LOCATION_SCOPE_ENTRY",
    )
