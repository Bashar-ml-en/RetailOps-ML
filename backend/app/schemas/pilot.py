"""Typed, non-secret pilot-readiness artifacts for authorised source preparation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


ReadinessStatus = Literal["PASS", "PASS_WITH_LIMITATIONS", "REJECT", "INCONCLUSIVE"]
RequestedAccess = Literal["READ_ONLY", "WRITE"]

REQUIRED_CSV_EXPORTS = frozenset(
    {"products", "locations", "order_lines", "inventory_snapshots"}
)


@dataclass(frozen=True)
class PilotReadinessRequest:
    """Declared Phase 0/1 facts only; this request contains no customer rows or credentials."""

    pilot_id: str
    tenant_id: str
    planner_owner_role: str
    data_owner_role: str
    security_approver_role: str
    authorization_reference: str
    authorization_attested: bool
    source_mode: str
    requested_access: RequestedAccess
    transfer_channel: str
    retention_rule: str
    category: str
    sku_scope: tuple[str, ...]
    location_scope: tuple[str, ...]
    operating_timezone: str
    forecast_horizon_days: int
    review_cadence: str
    current_planning_baseline: str
    historical_period_start: date | None
    historical_period_end: date | None
    header_sample_reference: str
    available_exports: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.pilot_id.strip():
            raise ValueError("pilot_id is required")
        if self.forecast_horizon_days < 1:
            raise ValueError("forecast_horizon_days must be positive")
        if self.historical_period_start and self.historical_period_end:
            if self.historical_period_end < self.historical_period_start:
                raise ValueError("historical_period_end must not be before historical_period_start")
        try:
            ZoneInfo(self.operating_timezone)
        except ZoneInfoNotFoundError as error:
            raise ValueError("operating_timezone must be an IANA timezone") from error


@dataclass(frozen=True)
class PilotReadinessAssessment:
    """Local audit artifact for pilot metadata readiness, never an access grant."""

    readiness_id: str
    assessed_at: datetime
    request: PilotReadinessRequest
    status: ReadinessStatus
    readiness_schema_version: str
    approved_uses: tuple[str, ...] = field(default_factory=tuple)
    blocked_uses: tuple[str, ...] = field(default_factory=tuple)
    limitations: tuple[str, ...] = field(default_factory=tuple)
    next_action: str = "stop"

    def to_dict(self) -> dict[str, object]:
        return {
            "readiness_schema_version": self.readiness_schema_version,
            "readiness_id": self.readiness_id,
            "assessed_at": self.assessed_at.isoformat(),
            "pilot_id": self.request.pilot_id,
            "tenant_id": self.request.tenant_id,
            "planner_owner_role": self.request.planner_owner_role,
            "data_owner_role": self.request.data_owner_role,
            "security_approver_role": self.request.security_approver_role,
            "authorization_reference": self.request.authorization_reference,
            "authorization_attested": self.request.authorization_attested,
            "source_mode": self.request.source_mode,
            "requested_access": self.request.requested_access,
            "transfer_channel": self.request.transfer_channel,
            "retention_rule": self.request.retention_rule,
            "category": self.request.category,
            "sku_scope": list(self.request.sku_scope),
            "location_scope": list(self.request.location_scope),
            "operating_timezone": self.request.operating_timezone,
            "forecast_horizon_days": self.request.forecast_horizon_days,
            "review_cadence": self.request.review_cadence,
            "current_planning_baseline": self.request.current_planning_baseline,
            "historical_period_start": (
                self.request.historical_period_start.isoformat()
                if self.request.historical_period_start
                else None
            ),
            "historical_period_end": (
                self.request.historical_period_end.isoformat()
                if self.request.historical_period_end
                else None
            ),
            "header_sample_reference": self.request.header_sample_reference,
            "available_exports": list(self.request.available_exports),
            "approved_uses": list(self.approved_uses),
            "blocked_uses": list(self.blocked_uses),
            "limitations": list(self.limitations),
            "next_action": self.next_action,
            "authorization_state": (
                "DECLARED_NOT_EXTERNALLY_VERIFIED"
                if self.request.authorization_attested and self.request.authorization_reference.strip()
                else "MISSING_OR_UNATTESTED"
            ),
            "customer_data_ingestion_permitted": False,
        }
