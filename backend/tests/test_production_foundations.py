"""Failure-closed P0 foundation-contract tests; no real infrastructure is invoked."""

from dataclasses import replace
from datetime import datetime, timezone

import pytest

from app.config import Settings
from app.schemas.foundation import (
    DisabledWorkerJob,
    FixtureTenantRoleDeclaration,
    FoundationResource,
    ProductionFoundationRequest,
)
from app.services.production_foundations import (
    DisabledTenantScopedScheduler,
    DisabledTenantScopedWorkerQueue,
    FixtureRoleScopeValidator,
    FoundationBoundaryError,
    ProductionFoundationRunner,
)
from app.services.storage import SnapshotStore


ASSESSMENT_TIME = datetime(2026, 9, 16, tzinfo=timezone.utc)


def complete_request(**overrides: object) -> ProductionFoundationRequest:
    resource_kinds = (
        "IDENTITY_PROVIDER",
        "SECRET_STORE",
        "RELATIONAL_AUDIT_STORE",
        "IMMUTABLE_OBJECT_STORE",
        "WORKER_QUEUE",
        "SCHEDULER",
        "ROLE_BASED_ACCESS",
    )
    values: dict[str, object] = {
        "foundation_id": "foundation-fixture-001",
        "tenant_isolation_strategy": "row-level-security-v1",
        "resources": tuple(
            FoundationResource(
                kind=kind,  # type: ignore[arg-type]
                reference=f"fixture:{kind.lower()}:v1",
                contract_version="v1",
            )
            for kind in resource_kinds
        ),
        "declared_roles": (
            "PLANNER",
            "DATA_OWNER",
            "SECURITY_APPROVER",
            "INGESTION_OPERATOR",
            "SERVICE_WORKER",
        ),
    }
    values.update(overrides)
    return ProductionFoundationRequest(**values)


def runner(store: SnapshotStore) -> ProductionFoundationRunner:
    return ProductionFoundationRunner(store, clock=lambda: ASSESSMENT_TIME)


def test_complete_foundation_declaration_is_persisted_but_remains_provisioning_only(tmp_path) -> None:
    store = SnapshotStore(tmp_path)

    assessment = runner(store).assess(complete_request())

    assert assessment.status == "PASS_WITH_LIMITATIONS"
    assert assessment.approved_uses == ("production_foundation_provisioning_plan",)
    assert "customer_data_ingestion" in assessment.blocked_uses
    assert "AUTHENTICATED_TENANT_RUNTIME_NOT_IMPLEMENTED" in assessment.limitations
    payload = assessment.to_dict()
    assert payload["customer_data_ingestion_permitted"] is False
    assert payload["worker_execution_permitted"] is False
    assert payload["external_execution_permitted"] is False
    persisted = store.load_production_foundation_assessment(assessment.assessment_id)
    assert persisted is not None
    assert persisted["status"] == "PASS_WITH_LIMITATIONS"
    assert persisted["resources"][0]["reference"] == "fixture:identity_provider:v1"


def test_missing_resource_and_required_role_is_inconclusive(tmp_path) -> None:
    store = SnapshotStore(tmp_path)
    request = complete_request(
        resources=complete_request().resources[:-1],
        declared_roles=("PLANNER",),
    )

    assessment = runner(store).assess(request)

    assert assessment.status == "INCONCLUSIVE"
    assert assessment.approved_uses == ()
    assert "MISSING_FOUNDATION_RESOURCE_ROLE_BASED_ACCESS" in assessment.limitations
    assert "MISSING_FOUNDATION_ROLE_DATA_OWNER" in assessment.limitations
    assert "MISSING_FOUNDATION_ROLE_SECURITY_APPROVER" in assessment.limitations
    assert "MISSING_FOUNDATION_ROLE_INGESTION_OPERATOR" in assessment.limitations


def test_activation_request_is_rejected_and_never_becomes_a_runtime_switch(tmp_path) -> None:
    store = SnapshotStore(tmp_path)

    assessment = runner(store).assess(
        replace(
            complete_request(),
            activation_requested=True,
            customer_data_ingestion_requested=True,
            worker_execution_requested=True,
        )
    )

    assert assessment.status == "REJECT"
    assert assessment.limitations == (
        "RUNTIME_ACTIVATION_PROHIBITED",
        "CUSTOMER_DATA_INGESTION_PROHIBITED",
        "WORKER_EXECUTION_PROHIBITED",
    )
    assert assessment.next_action == "keep_runtime_activation_disabled"


def test_fixture_role_scope_validation_blocks_cross_tenant_and_missing_role() -> None:
    declaration = FixtureTenantRoleDeclaration(
        tenant_id="fixture-tenant",
        principal_reference="fixture-planner",
        roles=("PLANNER",),
    )
    validator = FixtureRoleScopeValidator()

    validator.require_role(declaration, tenant_id="fixture-tenant", required_role="PLANNER")
    with pytest.raises(FoundationBoundaryError, match="TENANT_SCOPE_MISMATCH"):
        validator.require_role(declaration, tenant_id="other-tenant", required_role="PLANNER")
    with pytest.raises(FoundationBoundaryError, match="REQUIRED_ROLE_MISSING"):
        validator.require_role(declaration, tenant_id="fixture-tenant", required_role="DATA_OWNER")


def test_local_worker_and_scheduler_contracts_refuse_every_job_without_execution() -> None:
    job = DisabledWorkerJob(
        job_id="fixture-job-001",
        tenant_id="fixture-tenant",
        kind="REVIEW_WORKFLOW",
        evidence_refs=("fixture:evidence-bundle-v1",),
    )

    with pytest.raises(FoundationBoundaryError, match="WORKER_QUEUE_DISABLED_LOCAL_FOUNDATION"):
        DisabledTenantScopedWorkerQueue().enqueue(job)
    with pytest.raises(FoundationBoundaryError, match="SCHEDULER_DISABLED_LOCAL_FOUNDATION"):
        DisabledTenantScopedScheduler().schedule(job, "weekly-fixture-cadence")


def test_environment_cannot_claim_an_authenticated_tenant_runtime(monkeypatch) -> None:
    monkeypatch.setenv("RETAILOPS_ENABLE_CSV_INGESTION", "true")

    configured = Settings.from_environment()

    assert configured.csv_ingestion_enabled is True
    assert configured.authenticated_tenant_runtime_implemented is False


def test_foundation_declaration_rejects_credential_like_resource_values() -> None:
    with pytest.raises(ValueError, match="non-secret identifier"):
        FoundationResource(
            kind="SECRET_STORE",
            reference="secret=do-not-store-this",
            contract_version="v1",
        )
