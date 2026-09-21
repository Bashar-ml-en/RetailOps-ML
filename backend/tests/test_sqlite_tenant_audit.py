"""Tests for the local SQLite tenant-audit adapter and blocked durable job path."""

from datetime import datetime, timedelta, timezone

import pytest

from app.schemas.foundation import DisabledWorkerJob, FixtureTenantRoleDeclaration
from app.schemas.tenant_audit import TenantAuditEvent
from app.services.production_foundations import FoundationBoundaryError
from app.services.sqlite_tenant_audit import (
    TENANT_AUDIT_MIGRATION_VERSION,
    FixtureTenantAuditReader,
    SqliteFixtureTenantAuditStore,
    SqliteFixtureTenantJobQueue,
    SqliteFixtureTenantScheduler,
    TenantAuditStorageError,
)


AS_OF = datetime(2026, 9, 16, 12, 0, tzinfo=timezone.utc)


def declaration(tenant_id: str, roles: tuple[str, ...]) -> FixtureTenantRoleDeclaration:
    return FixtureTenantRoleDeclaration(
        tenant_id=tenant_id,
        principal_reference=f"fixture:{tenant_id}:principal",
        roles=roles,  # type: ignore[arg-type]
    )


def event(event_id: str, tenant_id: str, occurred_at: datetime = AS_OF) -> TenantAuditEvent:
    return TenantAuditEvent(
        event_id=event_id,
        tenant_id=tenant_id,
        occurred_at=occurred_at,
        name="FIXTURE_JOB_QUEUED",
        artifact_kind="WORKER_JOB",
        artifact_reference=f"job:{event_id}",
        limitations=("FIXTURE_ONLY",),
    )


def job(job_id: str, tenant_id: str) -> DisabledWorkerJob:
    return DisabledWorkerJob(
        job_id=job_id,
        tenant_id=tenant_id,
        kind="REVIEW_WORKFLOW",
        evidence_refs=("fixture:evidence-bundle-v1",),
    )


def test_migration_and_reader_keep_fixture_audit_events_tenant_partitioned(tmp_path) -> None:
    store = SqliteFixtureTenantAuditStore(tmp_path / "fixture-audit.sqlite3", clock=lambda: AS_OF)

    assert store.migrate() == (TENANT_AUDIT_MIGRATION_VERSION,)
    store.append_event(event("event-tenant-a", "tenant-a"))
    store.append_event(event("event-tenant-b", "tenant-b", AS_OF + timedelta(minutes=1)))
    reader = FixtureTenantAuditReader(store)

    tenant_a_events = reader.list_events(
        declaration("tenant-a", ("DATA_OWNER",)), "tenant-a"
    )

    assert [item.event_id for item in tenant_a_events] == ["event-tenant-a"]
    assert tenant_a_events[0].external_execution_permitted is False
    with pytest.raises(FoundationBoundaryError, match="TENANT_SCOPE_MISMATCH"):
        reader.list_events(declaration("tenant-a", ("DATA_OWNER",)), "tenant-b")


def test_audit_event_ids_are_immutable(tmp_path) -> None:
    store = SqliteFixtureTenantAuditStore(tmp_path / "fixture-audit.sqlite3", clock=lambda: AS_OF)
    stored_event = event("immutable-event", "tenant-a")

    store.append_event(stored_event)

    with pytest.raises(TenantAuditStorageError, match="AUDIT_EVENT_ALREADY_EXISTS"):
        store.append_event(stored_event)


def test_durable_fixture_job_has_a_matching_event_but_execution_stays_disabled(tmp_path) -> None:
    store = SqliteFixtureTenantAuditStore(tmp_path / "fixture-audit.sqlite3", clock=lambda: AS_OF)
    queue = SqliteFixtureTenantJobQueue(store, clock=lambda: AS_OF)
    actor = declaration("tenant-a", ("INGESTION_OPERATOR", "DATA_OWNER"))

    record = queue.enqueue(job("queue-job-001", "tenant-a"), actor)

    assert record.status == "QUEUED_BLOCKED"
    reader = FixtureTenantAuditReader(store)
    assert reader.list_jobs(actor, "tenant-a") == (record,)
    assert [item.name for item in reader.list_events(actor, "tenant-a")] == [
        "FIXTURE_JOB_QUEUED"
    ]
    with pytest.raises(FoundationBoundaryError, match="WORKER_EXECUTION_DISABLED_LOCAL_FIXTURE"):
        queue.claim_next("tenant-a")


def test_scheduler_persists_a_blocked_schedule_and_rejects_dispatch(tmp_path) -> None:
    store = SqliteFixtureTenantAuditStore(tmp_path / "fixture-audit.sqlite3", clock=lambda: AS_OF)
    scheduler = SqliteFixtureTenantScheduler(store, clock=lambda: AS_OF)
    actor = declaration("tenant-a", ("INGESTION_OPERATOR", "DATA_OWNER"))

    record = scheduler.schedule(job("schedule-job-001", "tenant-a"), "weekly-fixture", actor)

    assert record.status == "SCHEDULED_BLOCKED"
    assert record.cadence_reference == "weekly-fixture"
    with pytest.raises(FoundationBoundaryError, match="SCHEDULER_DISPATCH_DISABLED_LOCAL_FIXTURE"):
        scheduler.dispatch_due("tenant-a")


def test_job_submission_fails_closed_when_actor_role_is_missing(tmp_path) -> None:
    store = SqliteFixtureTenantAuditStore(tmp_path / "fixture-audit.sqlite3", clock=lambda: AS_OF)
    queue = SqliteFixtureTenantJobQueue(store, clock=lambda: AS_OF)

    with pytest.raises(FoundationBoundaryError, match="REQUIRED_ROLE_MISSING"):
        queue.enqueue(job("forbidden-job-001", "tenant-a"), declaration("tenant-a", ("DATA_OWNER",)))

    assert store.list_jobs("tenant-a") == ()
    assert store.list_events("tenant-a") == ()
