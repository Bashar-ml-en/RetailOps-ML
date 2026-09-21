"""Non-secret, failure-closed contracts for P0 production-foundation preparation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import re
from typing import Literal

from app.agents.contracts import DecisionStatus


FoundationResourceKind = Literal[
    "IDENTITY_PROVIDER",
    "SECRET_STORE",
    "RELATIONAL_AUDIT_STORE",
    "IMMUTABLE_OBJECT_STORE",
    "WORKER_QUEUE",
    "SCHEDULER",
    "ROLE_BASED_ACCESS",
]
FoundationRole = Literal[
    "PLANNER",
    "DATA_OWNER",
    "SECURITY_APPROVER",
    "INGESTION_OPERATOR",
    "SERVICE_WORKER",
]
FoundationJobKind = Literal[
    "CONNECTOR_INGESTION",
    "FORECAST_EVALUATION",
    "REVIEW_WORKFLOW",
    "MONITORING",
]

REQUIRED_FOUNDATION_RESOURCES = frozenset(
    {
        "IDENTITY_PROVIDER",
        "SECRET_STORE",
        "RELATIONAL_AUDIT_STORE",
        "IMMUTABLE_OBJECT_STORE",
        "WORKER_QUEUE",
        "SCHEDULER",
        "ROLE_BASED_ACCESS",
    }
)
_SAFE_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{1,127}$")
_SECRET_MARKERS = ("password=", "secret=", "token=", "api_key=", "authorization:")


def _require_safe_identifier(value: str, field: str) -> None:
    if not _SAFE_IDENTIFIER.fullmatch(value):
        raise ValueError(f"{field} must be a non-secret identifier")
    if any(marker in value.lower() for marker in _SECRET_MARKERS):
        raise ValueError(f"{field} must not contain a credential or secret")


@dataclass(frozen=True)
class FoundationResource:
    """A non-secret reference to a required future production resource."""

    kind: FoundationResourceKind
    reference: str
    contract_version: str

    def __post_init__(self) -> None:
        _require_safe_identifier(self.reference, "foundation resource reference")
        _require_safe_identifier(self.contract_version, "foundation resource contract_version")

    def to_dict(self) -> dict[str, str]:
        return {
            "kind": self.kind,
            "reference": self.reference,
            "contract_version": self.contract_version,
        }


@dataclass(frozen=True)
class ProductionFoundationRequest:
    """A provisioning declaration, never a customer-data or runtime activation request."""

    foundation_id: str
    tenant_isolation_strategy: str
    resources: tuple[FoundationResource, ...]
    declared_roles: tuple[FoundationRole, ...]
    activation_requested: bool = False
    customer_data_ingestion_requested: bool = False
    worker_execution_requested: bool = False
    data_classification: Literal["FIXTURE"] = "FIXTURE"

    def __post_init__(self) -> None:
        _require_safe_identifier(self.foundation_id, "foundation_id")
        _require_safe_identifier(self.tenant_isolation_strategy, "tenant_isolation_strategy")
        kinds = [resource.kind for resource in self.resources]
        if len(set(kinds)) != len(kinds):
            raise ValueError("foundation resource kinds must not be duplicated")
        if len(set(self.declared_roles)) != len(self.declared_roles):
            raise ValueError("declared_roles must not contain duplicates")


@dataclass(frozen=True)
class ProductionFoundationAssessment:
    """Immutable P0 readiness artifact; all results remain provisioning-only."""

    assessment_id: str
    assessed_at: datetime
    request: ProductionFoundationRequest
    status: DecisionStatus
    foundation_schema_version: Literal["production-foundation-v1"] = "production-foundation-v1"
    approved_uses: tuple[str, ...] = field(default_factory=tuple)
    blocked_uses: tuple[str, ...] = field(default_factory=tuple)
    limitations: tuple[str, ...] = field(default_factory=tuple)
    next_action: str = "stop"

    def __post_init__(self) -> None:
        if not self.assessment_id.strip():
            raise ValueError("assessment_id is required")
        if self.assessed_at.tzinfo is None:
            raise ValueError("assessed_at must include a timezone")
        if self.status == "PASS":
            raise ValueError("foundation preparation may not report an unrestricted PASS")

    def to_dict(self) -> dict[str, object]:
        return {
            "foundation_schema_version": self.foundation_schema_version,
            "assessment_id": self.assessment_id,
            "assessed_at": self.assessed_at.isoformat(),
            "foundation_id": self.request.foundation_id,
            "data_classification": self.request.data_classification,
            "tenant_isolation_strategy": self.request.tenant_isolation_strategy,
            "resources": [resource.to_dict() for resource in self.request.resources],
            "declared_roles": list(self.request.declared_roles),
            "status": self.status,
            "approved_uses": list(self.approved_uses),
            "blocked_uses": list(self.blocked_uses),
            "limitations": list(self.limitations),
            "next_action": self.next_action,
            "customer_data_ingestion_permitted": False,
            "worker_execution_permitted": False,
            "external_execution_permitted": False,
        }


@dataclass(frozen=True)
class FixtureTenantRoleDeclaration:
    """Fixture-only role shape; it is deliberately not an authentication credential."""

    tenant_id: str
    principal_reference: str
    roles: tuple[FoundationRole, ...]
    data_classification: Literal["FIXTURE"] = "FIXTURE"
    authenticated: Literal[False] = False

    def __post_init__(self) -> None:
        _require_safe_identifier(self.tenant_id, "tenant_id")
        _require_safe_identifier(self.principal_reference, "principal_reference")
        if not self.roles:
            raise ValueError("fixture role declaration requires at least one role")
        if len(set(self.roles)) != len(self.roles):
            raise ValueError("fixture role declaration must not duplicate roles")


@dataclass(frozen=True)
class DisabledWorkerJob:
    """A typed future-worker envelope that cannot be submitted by this release."""

    job_id: str
    tenant_id: str
    kind: FoundationJobKind
    evidence_refs: tuple[str, ...]
    data_classification: Literal["FIXTURE"] = "FIXTURE"
    external_execution_permitted: Literal[False] = False

    def __post_init__(self) -> None:
        _require_safe_identifier(self.job_id, "job_id")
        _require_safe_identifier(self.tenant_id, "tenant_id")
        if not self.evidence_refs:
            raise ValueError("disabled worker job requires named evidence references")
