"""Typed artifacts for RetailOps connector and benchmark snapshot runs."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal


IssueSeverity = Literal["ERROR", "LIMITATION"]
RunEventName = Literal[
    "QUEUED",
    "FETCHING",
    "VALIDATING",
    "SNAPSHOT_STORED",
    "DATA_CONTRACT_PASSED",
    "DATA_CONTRACT_LIMITED",
    "REJECTED",
    "INCONCLUSIVE",
    "FAILED",
]


@dataclass(frozen=True)
class ConnectorRunRequest:
    """Declared, non-secret context for one read-only CSV connector run."""

    tenant_id: str
    authorization_reference: str
    source_name: str = "authorised_csv_export"
    mapping_version: str = "csv-v1"
    as_of: datetime | None = None
    max_inventory_age_hours: int = 24

    def __post_init__(self) -> None:
        if not self.tenant_id.strip():
            raise ValueError("tenant_id is required")
        if not self.authorization_reference.strip():
            raise ValueError("authorization_reference is required")
        if self.max_inventory_age_hours <= 0:
            raise ValueError("max_inventory_age_hours must be positive")
        if self.as_of is not None and self.as_of.tzinfo is None:
            raise ValueError("as_of must include a timezone")


@dataclass(frozen=True)
class ConnectorIssue:
    severity: IssueSeverity
    code: str
    table: str
    row: int | None
    message: str

    def to_dict(self) -> dict[str, object]:
        return {
            "severity": self.severity,
            "code": self.code,
            "table": self.table,
            "row": self.row,
            "message": self.message,
        }


@dataclass(frozen=True)
class SnapshotManifest:
    snapshot_id: str
    tenant_id: str
    source_type: Literal["CSV", "PUBLIC_BENCHMARK"]
    source_name: str
    authorization_reference: str
    mapping_version: str
    retrieved_at: datetime
    source_hash: str
    schema_hash: str
    table_hashes: dict[str, str]
    row_counts: dict[str, int]
    excluded_counts: dict[str, int]
    data_classification: Literal["AUTHORISED_RETAILER", "PUBLIC_BENCHMARK"] = (
        "AUTHORISED_RETAILER"
    )
    source_reference: str | None = None
    license_reference: str | None = None
    issues: tuple[ConnectorIssue, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "snapshot_id": self.snapshot_id,
            "tenant_id": self.tenant_id,
            "source_type": self.source_type,
            "source_name": self.source_name,
            "authorization_reference": self.authorization_reference,
            "mapping_version": self.mapping_version,
            "data_classification": self.data_classification,
            "source_reference": self.source_reference,
            "license_reference": self.license_reference,
            "retrieved_at": self.retrieved_at.isoformat(),
            "source_hash": self.source_hash,
            "schema_hash": self.schema_hash,
            "table_hashes": self.table_hashes,
            "row_counts": self.row_counts,
            "excluded_counts": self.excluded_counts,
            "issues": [issue.to_dict() for issue in self.issues],
        }


@dataclass(frozen=True)
class DataContractResult:
    status: Literal["PASS", "PASS_WITH_LIMITATIONS", "REJECT", "INCONCLUSIVE"]
    approved_uses: tuple[str, ...]
    blocked_uses: tuple[str, ...]
    limitations: tuple[str, ...]
    next_action: str

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "approved_uses": list(self.approved_uses),
            "blocked_uses": list(self.blocked_uses),
            "limitations": list(self.limitations),
            "next_action": self.next_action,
        }


@dataclass(frozen=True)
class RunEvent:
    sequence: int
    name: RunEventName
    occurred_at: datetime
    detail: str
    evidence_refs: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "sequence": self.sequence,
            "name": self.name,
            "occurred_at": self.occurred_at.isoformat(),
            "detail": self.detail,
            "evidence_refs": list(self.evidence_refs),
        }


@dataclass(frozen=True)
class ConnectorRun:
    run_id: str
    request: ConnectorRunRequest
    manifest: SnapshotManifest | None
    result: DataContractResult
    agent_decision: dict[str, object] | None = None
    events: tuple[RunEvent, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, object]:
        return {
            "run_id": self.run_id,
            "source_type": self.manifest.source_type if self.manifest else "CSV",
            "tenant_id": self.request.tenant_id,
            "snapshot": self.manifest.to_dict() if self.manifest else None,
            "data_contract": self.result.to_dict(),
            "agent_decision": self.agent_decision,
            "events": [event.to_dict() for event in self.events],
        }
