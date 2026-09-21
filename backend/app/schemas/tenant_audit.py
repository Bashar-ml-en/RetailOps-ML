"""Fixture-only, tenant-partitioned audit and durable-job contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import re
from typing import Literal

from app.schemas.foundation import FoundationJobKind


TenantAuditArtifactKind = Literal[
    "FOUNDATION_ASSESSMENT",
    "WORKER_JOB",
    "WORKFLOW_RUN",
    "REVIEW_CASE",
    "MODEL_RUN",
    "CONNECTOR_RUN",
]
TenantAuditEventName = Literal[
    "FIXTURE_JOB_QUEUED",
    "FIXTURE_JOB_SCHEDULED",
    "FIXTURE_WORKER_EXECUTION_BLOCKED",
]
FixtureJobStatus = Literal["QUEUED_BLOCKED", "SCHEDULED_BLOCKED"]

_SAFE_REFERENCE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{1,127}$")


def _require_safe_reference(value: str, field: str) -> None:
    if not _SAFE_REFERENCE.fullmatch(value):
        raise ValueError(f"{field} must be a non-secret reference")


@dataclass(frozen=True)
class TenantAuditEvent:
    """A compact immutable event; raw rows, credentials, and payloads are excluded."""

    event_id: str
    tenant_id: str
    occurred_at: datetime
    name: TenantAuditEventName
    artifact_kind: TenantAuditArtifactKind
    artifact_reference: str
    limitations: tuple[str, ...] = ()
    data_classification: Literal["FIXTURE"] = "FIXTURE"
    external_execution_permitted: Literal[False] = False

    def __post_init__(self) -> None:
        _require_safe_reference(self.event_id, "event_id")
        _require_safe_reference(self.tenant_id, "tenant_id")
        _require_safe_reference(self.artifact_reference, "artifact_reference")
        if self.occurred_at.tzinfo is None:
            raise ValueError("occurred_at must include a timezone")

    def to_dict(self) -> dict[str, object]:
        return {
            "event_id": self.event_id,
            "tenant_id": self.tenant_id,
            "occurred_at": self.occurred_at.isoformat(),
            "name": self.name,
            "artifact_kind": self.artifact_kind,
            "artifact_reference": self.artifact_reference,
            "limitations": list(self.limitations),
            "data_classification": self.data_classification,
            "external_execution_permitted": self.external_execution_permitted,
        }


@dataclass(frozen=True)
class FixtureDurableJobRecord:
    """Persisted fixture job metadata; it represents no running or executable worker."""

    job_id: str
    tenant_id: str
    kind: FoundationJobKind
    created_at: datetime
    evidence_refs: tuple[str, ...]
    status: FixtureJobStatus
    cadence_reference: str | None = None
    data_classification: Literal["FIXTURE"] = "FIXTURE"
    external_execution_permitted: Literal[False] = False

    def __post_init__(self) -> None:
        _require_safe_reference(self.job_id, "job_id")
        _require_safe_reference(self.tenant_id, "tenant_id")
        if not self.evidence_refs:
            raise ValueError("fixture durable job requires named evidence references")
        for reference in self.evidence_refs:
            _require_safe_reference(reference, "job evidence reference")
        if self.cadence_reference is not None:
            _require_safe_reference(self.cadence_reference, "cadence_reference")
        if self.created_at.tzinfo is None:
            raise ValueError("created_at must include a timezone")

    def to_dict(self) -> dict[str, object]:
        return {
            "job_id": self.job_id,
            "tenant_id": self.tenant_id,
            "kind": self.kind,
            "created_at": self.created_at.isoformat(),
            "evidence_refs": list(self.evidence_refs),
            "status": self.status,
            "cadence_reference": self.cadence_reference,
            "data_classification": self.data_classification,
            "external_execution_permitted": self.external_execution_permitted,
        }
