"""P0 contracts that prepare, but never activate, production foundations."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from typing import Protocol
from uuid import uuid4

from app.schemas.foundation import (
    DisabledWorkerJob,
    FixtureTenantRoleDeclaration,
    FoundationRole,
    ProductionFoundationAssessment,
    ProductionFoundationRequest,
    REQUIRED_FOUNDATION_RESOURCES,
)
from app.services.storage import SnapshotStore


_BLOCKED_USES = (
    "customer_data_ingestion",
    "connector_activation",
    "production_worker_execution",
    "production_model_evaluation",
    "authenticated_reviewer_decision",
    "external_operation",
)


class FoundationBoundaryError(ValueError):
    """Raised when a P0 contract would be mistaken for an active production control."""


class TenantScopedJobQueue(Protocol):
    """Future adapter boundary; real adapters must authenticate and isolate every job."""

    def enqueue(self, job: DisabledWorkerJob) -> str: ...


class TenantScopedScheduler(Protocol):
    """Future adapter boundary; schedules must be tenant-scoped and auditable."""

    def schedule(self, job: DisabledWorkerJob, cadence_reference: str) -> str: ...


class ProductionFoundationRunner:
    """Assess declarative, non-secret P0 resource references and persist the result."""

    def __init__(
        self, store: SnapshotStore, clock: Callable[[], datetime] | None = None
    ) -> None:
        self.store = store
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def assess(self, request: ProductionFoundationRequest) -> ProductionFoundationAssessment:
        rejection_reasons = self._rejection_reasons(request)
        if rejection_reasons:
            assessment = self._assessment(
                request,
                status="REJECT",
                limitations=tuple(rejection_reasons),
                next_action="keep_runtime_activation_disabled",
            )
        else:
            missing = self._missing_requirements(request)
            if missing:
                assessment = self._assessment(
                    request,
                    status="INCONCLUSIVE",
                    limitations=tuple(missing),
                    next_action="complete_non_secret_foundation_declaration",
                )
            else:
                assessment = self._assessment(
                    request,
                    status="PASS_WITH_LIMITATIONS",
                    approved_uses=("production_foundation_provisioning_plan",),
                    limitations=(
                        "FIXTURE_FOUNDATION_DECLARATION_ONLY",
                        "RESOURCE_REFERENCES_NOT_EXTERNALLY_VERIFIED",
                        "AUTHENTICATED_TENANT_RUNTIME_NOT_IMPLEMENTED",
                        "CUSTOMER_DATA_AND_WORKER_ACTIVATION_BLOCKED",
                    ),
                    next_action="provision_and_verify_external_foundations_before_activation",
                )
        self.store.persist_production_foundation_assessment(assessment)
        return assessment

    @staticmethod
    def _rejection_reasons(request: ProductionFoundationRequest) -> list[str]:
        reasons: list[str] = []
        if request.data_classification != "FIXTURE":
            reasons.append("FOUNDATION_CONTRACT_FIXTURE_ONLY")
        if request.activation_requested:
            reasons.append("RUNTIME_ACTIVATION_PROHIBITED")
        if request.customer_data_ingestion_requested:
            reasons.append("CUSTOMER_DATA_INGESTION_PROHIBITED")
        if request.worker_execution_requested:
            reasons.append("WORKER_EXECUTION_PROHIBITED")
        return reasons

    @staticmethod
    def _missing_requirements(request: ProductionFoundationRequest) -> list[str]:
        limitations: list[str] = []
        resource_kinds = {resource.kind for resource in request.resources}
        for kind in sorted(REQUIRED_FOUNDATION_RESOURCES - resource_kinds):
            limitations.append(f"MISSING_FOUNDATION_RESOURCE_{kind}")
        required_roles = {"PLANNER", "DATA_OWNER", "SECURITY_APPROVER", "INGESTION_OPERATOR"}
        for role in sorted(required_roles - set(request.declared_roles)):
            limitations.append(f"MISSING_FOUNDATION_ROLE_{role}")
        return limitations

    def _assessment(
        self,
        request: ProductionFoundationRequest,
        *,
        status: str,
        limitations: tuple[str, ...],
        next_action: str,
        approved_uses: tuple[str, ...] = (),
    ) -> ProductionFoundationAssessment:
        return ProductionFoundationAssessment(
            assessment_id=str(uuid4()),
            assessed_at=self.clock(),
            request=request,
            status=status,  # type: ignore[arg-type]
            approved_uses=approved_uses,
            blocked_uses=_BLOCKED_USES,
            limitations=limitations,
            next_action=next_action,
        )


class FixtureRoleScopeValidator:
    """Validate a declared fixture role/scope without representing an identity provider."""

    def require_role(
        self,
        declaration: FixtureTenantRoleDeclaration,
        *,
        tenant_id: str,
        required_role: FoundationRole,
    ) -> None:
        if declaration.data_classification != "FIXTURE" or declaration.authenticated:
            raise FoundationBoundaryError("FIXTURE_ROLE_SCOPE_ONLY")
        if declaration.tenant_id != tenant_id:
            raise FoundationBoundaryError("TENANT_SCOPE_MISMATCH")
        if required_role not in declaration.roles:
            raise FoundationBoundaryError("REQUIRED_ROLE_MISSING")


class DisabledTenantScopedWorkerQueue:
    """The only queue adapter shipped locally: it refuses every job without side effects."""

    def enqueue(self, job: DisabledWorkerJob) -> str:
        raise FoundationBoundaryError(
            f"WORKER_QUEUE_DISABLED_LOCAL_FOUNDATION:{job.kind}:{job.tenant_id}"
        )


class DisabledTenantScopedScheduler:
    """The only scheduler adapter shipped locally: it refuses every schedule without side effects."""

    def schedule(self, job: DisabledWorkerJob, cadence_reference: str) -> str:
        if not cadence_reference.strip():
            raise FoundationBoundaryError("SCHEDULE_CADENCE_REFERENCE_REQUIRED")
        raise FoundationBoundaryError(
            f"SCHEDULER_DISABLED_LOCAL_FOUNDATION:{job.kind}:{job.tenant_id}"
        )
