"""SQLite fixture adapter for tenant-partitioned audit events and blocked jobs."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3

from app.schemas.foundation import DisabledWorkerJob, FixtureTenantRoleDeclaration
from app.schemas.tenant_audit import FixtureDurableJobRecord, TenantAuditEvent
from app.services.production_foundations import FoundationBoundaryError, FixtureRoleScopeValidator


TENANT_AUDIT_MIGRATION_VERSION = "fixture-tenant-audit-v1"


class TenantAuditStorageError(ValueError):
    """Raised when the local SQLite audit adapter would violate its immutable boundary."""


class SqliteFixtureTenantAuditStore:
    """Persist metadata-only fixture events/jobs in a tenant-partitioned SQLite file.

    This adapter is useful for migration and repository tests. It is not a
    production audit database, has no authenticated connection, and must not
    receive customer data or credentials.
    """

    def __init__(self, database_path: Path, clock: Callable[[], datetime] | None = None) -> None:
        self.database_path = database_path
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def migrate(self) -> tuple[str, ...]:
        """Apply the one idempotent local schema migration and return versions present."""

        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version TEXT PRIMARY KEY NOT NULL,
                    applied_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS tenant_audit_events (
                    event_id TEXT PRIMARY KEY NOT NULL,
                    tenant_id TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    name TEXT NOT NULL,
                    artifact_kind TEXT NOT NULL,
                    artifact_reference TEXT NOT NULL,
                    limitations_json TEXT NOT NULL,
                    data_classification TEXT NOT NULL CHECK (data_classification = 'FIXTURE'),
                    external_execution_permitted INTEGER NOT NULL CHECK (external_execution_permitted = 0)
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS tenant_audit_events_tenant_time
                ON tenant_audit_events (tenant_id, occurred_at, event_id)
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS fixture_durable_jobs (
                    job_id TEXT PRIMARY KEY NOT NULL,
                    tenant_id TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    evidence_refs_json TEXT NOT NULL,
                    status TEXT NOT NULL CHECK (status IN ('QUEUED_BLOCKED', 'SCHEDULED_BLOCKED')),
                    cadence_reference TEXT,
                    data_classification TEXT NOT NULL CHECK (data_classification = 'FIXTURE'),
                    external_execution_permitted INTEGER NOT NULL CHECK (external_execution_permitted = 0)
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS fixture_durable_jobs_tenant_time
                ON fixture_durable_jobs (tenant_id, created_at, job_id)
                """
            )
            connection.execute(
                "INSERT OR IGNORE INTO schema_migrations (version, applied_at) VALUES (?, ?)",
                (TENANT_AUDIT_MIGRATION_VERSION, self.clock().isoformat()),
            )
            rows = connection.execute(
                "SELECT version FROM schema_migrations ORDER BY version"
            ).fetchall()
        return tuple(str(row["version"]) for row in rows)

    def append_event(self, event: TenantAuditEvent) -> None:
        self.migrate()
        try:
            with self._connect() as connection:
                connection.execute(
                    """
                    INSERT INTO tenant_audit_events (
                        event_id, tenant_id, occurred_at, name, artifact_kind,
                        artifact_reference, limitations_json, data_classification,
                        external_execution_permitted
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event.event_id,
                        event.tenant_id,
                        event.occurred_at.isoformat(),
                        event.name,
                        event.artifact_kind,
                        event.artifact_reference,
                        json.dumps(event.limitations),
                        event.data_classification,
                        int(event.external_execution_permitted),
                    ),
                )
        except sqlite3.IntegrityError as error:
            raise TenantAuditStorageError("AUDIT_EVENT_ALREADY_EXISTS") from error

    def list_events(self, tenant_id: str) -> tuple[TenantAuditEvent, ...]:
        self.migrate()
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT event_id, tenant_id, occurred_at, name, artifact_kind,
                       artifact_reference, limitations_json, data_classification,
                       external_execution_permitted
                FROM tenant_audit_events
                WHERE tenant_id = ?
                ORDER BY occurred_at, event_id
                """,
                (tenant_id,),
            ).fetchall()
        return tuple(
            TenantAuditEvent(
                event_id=str(row["event_id"]),
                tenant_id=str(row["tenant_id"]),
                occurred_at=self._parse_timestamp(row["occurred_at"], "occurred_at"),
                name=str(row["name"]),  # type: ignore[arg-type]
                artifact_kind=str(row["artifact_kind"]),  # type: ignore[arg-type]
                artifact_reference=str(row["artifact_reference"]),
                limitations=tuple(str(item) for item in json.loads(str(row["limitations_json"]))),
                data_classification=str(row["data_classification"]),  # type: ignore[arg-type]
                external_execution_permitted=bool(row["external_execution_permitted"]),  # type: ignore[arg-type]
            )
            for row in rows
        )

    def persist_job(self, job: FixtureDurableJobRecord) -> None:
        self.migrate()
        try:
            with self._connect() as connection:
                connection.execute(
                    """
                    INSERT INTO fixture_durable_jobs (
                        job_id, tenant_id, kind, created_at, evidence_refs_json,
                        status, cadence_reference, data_classification,
                        external_execution_permitted
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        job.job_id,
                        job.tenant_id,
                        job.kind,
                        job.created_at.isoformat(),
                        json.dumps(job.evidence_refs),
                        job.status,
                        job.cadence_reference,
                        job.data_classification,
                        int(job.external_execution_permitted),
                    ),
                )
        except sqlite3.IntegrityError as error:
            raise TenantAuditStorageError("FIXTURE_JOB_ALREADY_EXISTS") from error

    def persist_job_with_event(
        self, job: FixtureDurableJobRecord, event: TenantAuditEvent
    ) -> None:
        """Atomically store one blocked fixture job and its corresponding audit event."""

        if (
            event.tenant_id != job.tenant_id
            or event.artifact_kind != "WORKER_JOB"
            or event.artifact_reference != f"job:{job.job_id}"
        ):
            raise TenantAuditStorageError("JOB_EVENT_TENANT_OR_REFERENCE_MISMATCH")
        self.migrate()
        try:
            with self._connect() as connection:
                connection.execute(
                    """
                    INSERT INTO fixture_durable_jobs (
                        job_id, tenant_id, kind, created_at, evidence_refs_json,
                        status, cadence_reference, data_classification,
                        external_execution_permitted
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        job.job_id,
                        job.tenant_id,
                        job.kind,
                        job.created_at.isoformat(),
                        json.dumps(job.evidence_refs),
                        job.status,
                        job.cadence_reference,
                        job.data_classification,
                        int(job.external_execution_permitted),
                    ),
                )
                connection.execute(
                    """
                    INSERT INTO tenant_audit_events (
                        event_id, tenant_id, occurred_at, name, artifact_kind,
                        artifact_reference, limitations_json, data_classification,
                        external_execution_permitted
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event.event_id,
                        event.tenant_id,
                        event.occurred_at.isoformat(),
                        event.name,
                        event.artifact_kind,
                        event.artifact_reference,
                        json.dumps(event.limitations),
                        event.data_classification,
                        int(event.external_execution_permitted),
                    ),
                )
        except sqlite3.IntegrityError as error:
            raise TenantAuditStorageError("FIXTURE_JOB_OR_EVENT_ALREADY_EXISTS") from error

    def list_jobs(self, tenant_id: str) -> tuple[FixtureDurableJobRecord, ...]:
        self.migrate()
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT job_id, tenant_id, kind, created_at, evidence_refs_json,
                       status, cadence_reference, data_classification,
                       external_execution_permitted
                FROM fixture_durable_jobs
                WHERE tenant_id = ?
                ORDER BY created_at, job_id
                """,
                (tenant_id,),
            ).fetchall()
        return tuple(
            FixtureDurableJobRecord(
                job_id=str(row["job_id"]),
                tenant_id=str(row["tenant_id"]),
                kind=str(row["kind"]),  # type: ignore[arg-type]
                created_at=self._parse_timestamp(row["created_at"], "created_at"),
                evidence_refs=tuple(
                    str(item) for item in json.loads(str(row["evidence_refs_json"]))
                ),
                status=str(row["status"]),  # type: ignore[arg-type]
                cadence_reference=(
                    str(row["cadence_reference"])
                    if row["cadence_reference"] is not None
                    else None
                ),
                data_classification=str(row["data_classification"]),  # type: ignore[arg-type]
                external_execution_permitted=bool(row["external_execution_permitted"]),  # type: ignore[arg-type]
            )
            for row in rows
        )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    @staticmethod
    def _parse_timestamp(value: object, field: str) -> datetime:
        if not isinstance(value, str):
            raise TenantAuditStorageError(f"TENANT_AUDIT_RECORD_MALFORMED:{field}")
        try:
            timestamp = datetime.fromisoformat(value)
        except ValueError as error:
            raise TenantAuditStorageError(f"TENANT_AUDIT_RECORD_MALFORMED:{field}") from error
        if timestamp.tzinfo is None:
            raise TenantAuditStorageError(f"TENANT_AUDIT_RECORD_MALFORMED:{field}")
        return timestamp


class FixtureTenantAuditReader:
    """Read fixture tenant partitions only after a labelled role/scope check."""

    def __init__(
        self, store: SqliteFixtureTenantAuditStore, validator: FixtureRoleScopeValidator | None = None
    ) -> None:
        self.store = store
        self.validator = validator or FixtureRoleScopeValidator()

    def list_events(
        self, declaration: FixtureTenantRoleDeclaration, tenant_id: str
    ) -> tuple[TenantAuditEvent, ...]:
        self.validator.require_role(
            declaration, tenant_id=tenant_id, required_role="DATA_OWNER"
        )
        return self.store.list_events(tenant_id)

    def list_jobs(
        self, declaration: FixtureTenantRoleDeclaration, tenant_id: str
    ) -> tuple[FixtureDurableJobRecord, ...]:
        self.validator.require_role(
            declaration, tenant_id=tenant_id, required_role="DATA_OWNER"
        )
        return self.store.list_jobs(tenant_id)


class SqliteFixtureTenantJobQueue:
    """Durably record a fixture submission while leaving execution terminally disabled."""

    def __init__(
        self,
        store: SqliteFixtureTenantAuditStore,
        clock: Callable[[], datetime] | None = None,
        validator: FixtureRoleScopeValidator | None = None,
    ) -> None:
        self.store = store
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.validator = validator or FixtureRoleScopeValidator()

    def enqueue(
        self, job: DisabledWorkerJob, declaration: FixtureTenantRoleDeclaration
    ) -> FixtureDurableJobRecord:
        self.validator.require_role(
            declaration, tenant_id=job.tenant_id, required_role="INGESTION_OPERATOR"
        )
        record = FixtureDurableJobRecord(
            job_id=job.job_id,
            tenant_id=job.tenant_id,
            kind=job.kind,
            created_at=self.clock(),
            evidence_refs=job.evidence_refs,
            status="QUEUED_BLOCKED",
        )
        self.store.persist_job_with_event(
            record,
            TenantAuditEvent(
                event_id=f"audit:{job.job_id}:queued",
                tenant_id=job.tenant_id,
                occurred_at=record.created_at,
                name="FIXTURE_JOB_QUEUED",
                artifact_kind="WORKER_JOB",
                artifact_reference=f"job:{job.job_id}",
                limitations=("WORKER_EXECUTION_DISABLED_LOCAL_FIXTURE",),
            ),
        )
        return record

    def claim_next(self, tenant_id: str) -> None:
        raise FoundationBoundaryError(f"WORKER_EXECUTION_DISABLED_LOCAL_FIXTURE:{tenant_id}")


class SqliteFixtureTenantScheduler:
    """Durably record a fixture schedule while leaving dispatch terminally disabled."""

    def __init__(
        self,
        store: SqliteFixtureTenantAuditStore,
        clock: Callable[[], datetime] | None = None,
        validator: FixtureRoleScopeValidator | None = None,
    ) -> None:
        self.store = store
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.validator = validator or FixtureRoleScopeValidator()

    def schedule(
        self,
        job: DisabledWorkerJob,
        cadence_reference: str,
        declaration: FixtureTenantRoleDeclaration,
    ) -> FixtureDurableJobRecord:
        self.validator.require_role(
            declaration, tenant_id=job.tenant_id, required_role="INGESTION_OPERATOR"
        )
        record = FixtureDurableJobRecord(
            job_id=job.job_id,
            tenant_id=job.tenant_id,
            kind=job.kind,
            created_at=self.clock(),
            evidence_refs=job.evidence_refs,
            status="SCHEDULED_BLOCKED",
            cadence_reference=cadence_reference,
        )
        self.store.persist_job_with_event(
            record,
            TenantAuditEvent(
                event_id=f"audit:{job.job_id}:scheduled",
                tenant_id=job.tenant_id,
                occurred_at=record.created_at,
                name="FIXTURE_JOB_SCHEDULED",
                artifact_kind="WORKER_JOB",
                artifact_reference=f"job:{job.job_id}",
                limitations=("SCHEDULER_DISPATCH_DISABLED_LOCAL_FIXTURE",),
            ),
        )
        return record

    def dispatch_due(self, tenant_id: str) -> None:
        raise FoundationBoundaryError(f"SCHEDULER_DISPATCH_DISABLED_LOCAL_FIXTURE:{tenant_id}")
