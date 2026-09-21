"""Deterministic Phase 0/1 readiness checks without customer-data ingestion."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable
from uuid import uuid4

from app.schemas.pilot import (
    REQUIRED_CSV_EXPORTS,
    PilotReadinessAssessment,
    PilotReadinessRequest,
)


PILOT_READINESS_SCHEMA_VERSION = "pilot-readiness-v1"
_CUSTOMER_DATA_BLOCKED_USES = (
    "customer_data_ingestion",
    "demand_forecast",
    "production_scoring",
    "replenishment_draft",
)


class PilotReadinessRunner:
    """Check declared pilot metadata and keep authorisation claims fail-closed.

    A complete local assessment permits only source-mapping preparation. It
    never verifies an external approval, enables a connector, or permits an
    operational data upload.
    """

    def __init__(self, clock: Callable[[], datetime] | None = None) -> None:
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def assess(self, request: PilotReadinessRequest) -> PilotReadinessAssessment:
        rejection_reasons = self._rejection_reasons(request)
        if rejection_reasons:
            return self._assessment(
                request,
                status="REJECT",
                limitations=tuple(rejection_reasons),
                next_action="correct_access_boundary",
            )

        missing_evidence = self._missing_evidence(request)
        if missing_evidence:
            return self._assessment(
                request,
                status="INCONCLUSIVE",
                limitations=tuple(missing_evidence),
                next_action="provide_missing_pilot_charter_evidence",
            )

        scope_limitations = self._scope_limitations(request)
        if scope_limitations:
            return self._assessment(
                request,
                status="INCONCLUSIVE",
                limitations=tuple(scope_limitations),
                next_action="declare_approved_pilot_cohort",
            )

        return self._assessment(
            request,
            status="PASS_WITH_LIMITATIONS",
            approved_uses=("pilot_source_mapping",),
            limitations=(
                "AUTHORIZATION_REFERENCE_DECLARED_NOT_EXTERNALLY_VERIFIED",
                "AUTHENTICATED_TENANT_DEPLOYMENT_REQUIRED_BEFORE_INGESTION",
            ),
            next_action="configure_authenticated_tenant_scope",
        )

    @staticmethod
    def _rejection_reasons(request: PilotReadinessRequest) -> list[str]:
        reasons: list[str] = []
        if request.source_mode.strip().upper() != "CSV":
            reasons.append("FIRST_PILOT_REQUIRES_READ_ONLY_CSV")
        if request.requested_access != "READ_ONLY":
            reasons.append("REQUESTED_ACCESS_NOT_READ_ONLY")
        return reasons

    @staticmethod
    def _missing_evidence(request: PilotReadinessRequest) -> list[str]:
        required_fields = {
            "tenant_id": request.tenant_id,
            "planner_owner_role": request.planner_owner_role,
            "data_owner_role": request.data_owner_role,
            "security_approver_role": request.security_approver_role,
            "authorization_reference": request.authorization_reference,
            "transfer_channel": request.transfer_channel,
            "retention_rule": request.retention_rule,
            "category": request.category,
            "review_cadence": request.review_cadence,
            "current_planning_baseline": request.current_planning_baseline,
            "header_sample_reference": request.header_sample_reference,
        }
        missing = [
            f"MISSING_{field.upper()}" for field, value in required_fields.items() if not value.strip()
        ]
        if not request.authorization_attested:
            missing.append("AUTHORIZATION_NOT_ATTESTED")
        if request.historical_period_start is None or request.historical_period_end is None:
            missing.append("MISSING_DECLARED_HISTORICAL_PERIOD")
        if not REQUIRED_CSV_EXPORTS.issubset({item.strip().lower() for item in request.available_exports}):
            missing.append("MISSING_REQUIRED_CSV_EXPORT_DECLARATION")
        return missing

    @staticmethod
    def _scope_limitations(request: PilotReadinessRequest) -> list[str]:
        limitations: list[str] = []
        if not 20 <= len(request.sku_scope) <= 50:
            limitations.append("SKU_SCOPE_OUTSIDE_DECLARED_PILOT_TARGET")
        if not 1 <= len(request.location_scope) <= 3:
            limitations.append("LOCATION_SCOPE_OUTSIDE_DECLARED_PILOT_TARGET")
        if any(not item.strip() for item in request.sku_scope):
            limitations.append("BLANK_SKU_SCOPE_ENTRY")
        if any(not item.strip() for item in request.location_scope):
            limitations.append("BLANK_LOCATION_SCOPE_ENTRY")
        if len({item.strip() for item in request.sku_scope}) != len(request.sku_scope):
            limitations.append("DUPLICATE_SKU_SCOPE_ENTRY")
        if len({item.strip() for item in request.location_scope}) != len(request.location_scope):
            limitations.append("DUPLICATE_LOCATION_SCOPE_ENTRY")
        if request.review_cadence.strip().upper() != "WEEKLY":
            limitations.append("REVIEW_CADENCE_MUST_BE_WEEKLY_FOR_FIRST_PILOT")
        return limitations

    def _assessment(
        self,
        request: PilotReadinessRequest,
        *,
        status: str,
        approved_uses: tuple[str, ...] = (),
        limitations: tuple[str, ...],
        next_action: str,
    ) -> PilotReadinessAssessment:
        return PilotReadinessAssessment(
            readiness_id=str(uuid4()),
            assessed_at=self.clock(),
            request=request,
            status=status,  # type: ignore[arg-type]
            readiness_schema_version=PILOT_READINESS_SCHEMA_VERSION,
            approved_uses=approved_uses,
            blocked_uses=_CUSTOMER_DATA_BLOCKED_USES,
            limitations=limitations,
            next_action=next_action,
        )
