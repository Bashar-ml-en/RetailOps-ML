"""Typed, deterministic review-case contracts for the Stage 5 specialists."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

from app.agents.contracts import AgentDecision, DecisionStatus


ReviewDataClassification = Literal["AUTHORISED_RETAILER", "PUBLIC_BENCHMARK", "FIXTURE"]
RequestedAction = Literal["HUMAN_REVIEW", "EXTERNAL_OPERATION"]
ReviewDecisionOutcome = Literal["APPROVE", "DECLINE", "DEFER"]
ReviewCaseState = Literal["READY_FOR_REVIEW", "DEFERRED", "APPROVED", "DECLINED"]


def decision_payload(decision: AgentDecision) -> dict[str, object]:
    return {
        "agent": decision.agent,
        "run_id": decision.run_id,
        "status": decision.status,
        "findings": [
            {"statement": finding.statement, "evidence_refs": list(finding.evidence_refs)}
            for finding in decision.findings
        ],
        "limitations": list(decision.limitations),
        "next_action": decision.next_action,
    }


@dataclass(frozen=True)
class ReviewScope:
    """Compatible identity for a single reviewable SKU-location-unit scope."""

    tenant_id: str
    snapshot_id: str
    sku: str
    location_id: str
    quantity_unit: str

    def __post_init__(self) -> None:
        if not all(
            value.strip()
            for value in (self.tenant_id, self.snapshot_id, self.sku, self.location_id, self.quantity_unit)
        ):
            raise ValueError("review scope tenant, snapshot, SKU, location, and unit are required")

    @property
    def scope_ref(self) -> str:
        return f"sku:{self.sku}|location:{self.location_id}|unit:{self.quantity_unit}"


@dataclass(frozen=True)
class ForecastEvidence:
    """A versioned forecast quantity whose source remains inspectable."""

    model_run_id: str
    model_version: str
    horizon_days: int
    forecast_quantity: float

    def __post_init__(self) -> None:
        if not self.model_run_id.strip() or not self.model_version.strip():
            raise ValueError("forecast model run and version are required")
        if self.horizon_days <= 0:
            raise ValueError("forecast horizon_days must be positive")
        if self.forecast_quantity < 0:
            raise ValueError("forecast_quantity must be non-negative")


@dataclass(frozen=True)
class InboundSupplyEvidence:
    """Declared, read-only supply evidence; an empty complete list means none is expected."""

    supply_id: str
    expected_at: datetime
    quantity: float
    confirmed: bool

    def __post_init__(self) -> None:
        if not self.supply_id.strip():
            raise ValueError("supply_id is required")
        if self.expected_at.tzinfo is None:
            raise ValueError("expected_at must include a timezone")
        if self.quantity < 0:
            raise ValueError("inbound supply quantity must be non-negative")


@dataclass(frozen=True)
class InventoryRiskRequest:
    """Evidence required to qualify a stock-risk review case without guessing."""

    run_id: str
    data_classification: ReviewDataClassification
    scope: ReviewScope
    forecast: ForecastEvidence
    as_of: datetime
    data_contract_status: DecisionStatus
    forecast_evaluation_status: DecisionStatus
    inventory_observed_at: datetime | None = None
    on_hand_quantity: float | None = None
    inbound_supply: tuple[InboundSupplyEvidence, ...] = ()
    inbound_supply_complete: bool = False
    lead_time_days: int | None = None
    max_inventory_age_hours: int = 24

    def __post_init__(self) -> None:
        if not self.run_id.strip():
            raise ValueError("run_id is required")
        if self.as_of.tzinfo is None:
            raise ValueError("as_of must include a timezone")
        if self.inventory_observed_at is not None and self.inventory_observed_at.tzinfo is None:
            raise ValueError("inventory_observed_at must include a timezone")
        if self.on_hand_quantity is not None and self.on_hand_quantity < 0:
            raise ValueError("on_hand_quantity must be non-negative")
        if self.max_inventory_age_hours <= 0:
            raise ValueError("max_inventory_age_hours must be positive")


@dataclass(frozen=True)
class InventoryRiskDecision:
    """Deterministic evidence outcome for inventory-risk qualification."""

    agent_decision: AgentDecision
    data_classification: ReviewDataClassification
    scope: ReviewScope
    risk_case_qualified: bool | None = None
    forecast_daily_rate: float | None = None
    demand_during_lead_time: float | None = None
    confirmed_supply_during_lead_time: float | None = None
    shortfall_quantity: float | None = None
    coverage_days: float | None = None

    @property
    def status(self) -> DecisionStatus:
        return self.agent_decision.status

    def to_dict(self) -> dict[str, object]:
        return {
            "decision": decision_payload(self.agent_decision),
            "data_classification": self.data_classification,
            "scope": {
                "tenant_id": self.scope.tenant_id,
                "snapshot_id": self.scope.snapshot_id,
                "sku": self.scope.sku,
                "location_id": self.scope.location_id,
                "quantity_unit": self.scope.quantity_unit,
            },
            "risk_case_qualified": self.risk_case_qualified,
            "forecast_daily_rate": self.forecast_daily_rate,
            "demand_during_lead_time": self.demand_during_lead_time,
            "confirmed_supply_during_lead_time": self.confirmed_supply_during_lead_time,
            "shortfall_quantity": self.shortfall_quantity,
            "coverage_days": self.coverage_days,
        }


@dataclass(frozen=True)
class ImpactRankingRequest:
    """Rank already-qualified cases without inferring financial benefit."""

    run_id: str
    data_classification: ReviewDataClassification
    risk_cases: tuple[InventoryRiskDecision, ...]
    ranking_policy_version: str = "shortfall-then-coverage-v1"

    def __post_init__(self) -> None:
        if not self.run_id.strip():
            raise ValueError("run_id is required")
        if not self.ranking_policy_version.strip():
            raise ValueError("ranking_policy_version is required")


@dataclass(frozen=True)
class RankedReviewCase:
    """A non-financial priority ordering for a qualified human-review case."""

    rank: int
    scope: ReviewScope
    shortfall_quantity: float
    coverage_days: float
    evidence_refs: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "rank": self.rank,
            "scope": {
                "tenant_id": self.scope.tenant_id,
                "snapshot_id": self.scope.snapshot_id,
                "sku": self.scope.sku,
                "location_id": self.scope.location_id,
                "quantity_unit": self.scope.quantity_unit,
            },
            "shortfall_quantity": self.shortfall_quantity,
            "coverage_days": self.coverage_days,
            "evidence_refs": list(self.evidence_refs),
        }


@dataclass(frozen=True)
class ImpactRankingDecision:
    """Deterministic ordering that never claims revenue, profit, or availability impact."""

    agent_decision: AgentDecision
    data_classification: ReviewDataClassification
    ranking_policy_version: str
    ranked_cases: tuple[RankedReviewCase, ...] = ()

    @property
    def status(self) -> DecisionStatus:
        return self.agent_decision.status

    def to_dict(self) -> dict[str, object]:
        return {
            "decision": decision_payload(self.agent_decision),
            "data_classification": self.data_classification,
            "ranking_policy_version": self.ranking_policy_version,
            "ranked_cases": [case.to_dict() for case in self.ranked_cases],
        }


@dataclass(frozen=True)
class PolicyCriticRequest:
    """All evidence required before a human-review draft can be considered."""

    run_id: str
    data_classification: ReviewDataClassification
    data_contract_status: DecisionStatus
    forecast_evaluation_status: DecisionStatus
    inventory_risk: InventoryRiskDecision
    impact_ranking: ImpactRankingDecision
    requested_action: RequestedAction = "HUMAN_REVIEW"

    def __post_init__(self) -> None:
        if not self.run_id.strip():
            raise ValueError("run_id is required")


@dataclass(frozen=True)
class PolicyCriticDecision:
    """The veto gate; only a critic-approved case may be drafted for review."""

    agent_decision: AgentDecision
    data_classification: ReviewDataClassification
    approved_for_action_draft: bool = False

    @property
    def status(self) -> DecisionStatus:
        return self.agent_decision.status

    def to_dict(self) -> dict[str, object]:
        return {
            "decision": decision_payload(self.agent_decision),
            "data_classification": self.data_classification,
            "approved_for_action_draft": self.approved_for_action_draft,
        }


@dataclass(frozen=True)
class ActionDraftRequest:
    """Request for a planner-review draft, never an external execution instruction."""

    run_id: str
    data_classification: ReviewDataClassification
    planner_owner_role: str
    inventory_risk: InventoryRiskDecision
    impact_ranking: ImpactRankingDecision
    policy_critic: PolicyCriticDecision

    def __post_init__(self) -> None:
        if not self.run_id.strip() or not self.planner_owner_role.strip():
            raise ValueError("run_id and planner_owner_role are required")


@dataclass(frozen=True)
class PlannerReviewDraft:
    """A concise review prompt with no provider write or operational execution authority."""

    case_id: str
    planner_owner_role: str
    summary: str
    requested_human_decision: Literal["APPROVE", "DECLINE", "DEFER"] = "APPROVE"
    external_execution_permitted: Literal[False] = False

    def to_dict(self) -> dict[str, object]:
        return {
            "case_id": self.case_id,
            "planner_owner_role": self.planner_owner_role,
            "summary": self.summary,
            "requested_human_decision": self.requested_human_decision,
            "external_execution_permitted": self.external_execution_permitted,
        }


@dataclass(frozen=True)
class ActionDraftDecision:
    """Final local contract outcome; a missing or vetoed case has no draft."""

    agent_decision: AgentDecision
    data_classification: ReviewDataClassification
    draft: PlannerReviewDraft | None = None
    limitations: tuple[str, ...] = field(default_factory=tuple)

    @property
    def status(self) -> DecisionStatus:
        return self.agent_decision.status

    def to_dict(self) -> dict[str, object]:
        return {
            "decision": decision_payload(self.agent_decision),
            "data_classification": self.data_classification,
            "draft": self.draft.to_dict() if self.draft else None,
            "limitations": list(self.limitations),
        }


@dataclass(frozen=True)
class ReviewCase:
    """An immutable, fixture-only case waiting for a human-review decision."""

    case_id: str
    created_at: datetime
    data_classification: Literal["FIXTURE"]
    scope: ReviewScope
    planner_owner_role: str
    draft: PlannerReviewDraft
    policy_critic_run_id: str
    evidence_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.case_id.strip() or not self.planner_owner_role.strip():
            raise ValueError("case_id and planner_owner_role are required")
        if self.data_classification != "FIXTURE":
            raise ValueError("local review cases must be explicitly labelled FIXTURE")
        if self.created_at.tzinfo is None:
            raise ValueError("created_at must include a timezone")
        if self.draft.external_execution_permitted:
            raise ValueError("review cases cannot permit external execution")

    def to_dict(self) -> dict[str, object]:
        return {
            "case_id": self.case_id,
            "created_at": self.created_at.isoformat(),
            "data_classification": self.data_classification,
            "scope": {
                "tenant_id": self.scope.tenant_id,
                "snapshot_id": self.scope.snapshot_id,
                "sku": self.scope.sku,
                "location_id": self.scope.location_id,
                "quantity_unit": self.scope.quantity_unit,
            },
            "planner_owner_role": self.planner_owner_role,
            "draft": self.draft.to_dict(),
            "policy_critic_run_id": self.policy_critic_run_id,
            "evidence_refs": list(self.evidence_refs),
            "external_execution_permitted": False,
        }


@dataclass(frozen=True)
class ReviewDecisionRequest:
    """A human-review outcome recorded as an immutable local audit event."""

    case_id: str
    planner_owner_role: str
    outcome: ReviewDecisionOutcome
    reason: str

    def __post_init__(self) -> None:
        if not all(value.strip() for value in (self.case_id, self.planner_owner_role, self.reason)):
            raise ValueError("case_id, planner_owner_role, and reason are required")


@dataclass(frozen=True)
class ReviewDecisionEvent:
    """A non-executing planner decision that is append-only in local audit storage."""

    decision_id: str
    case_id: str
    recorded_at: datetime
    planner_owner_role: str
    outcome: ReviewDecisionOutcome
    reason: str
    external_execution_permitted: Literal[False] = False

    def __post_init__(self) -> None:
        if not self.decision_id.strip() or not self.case_id.strip() or not self.planner_owner_role.strip():
            raise ValueError("decision_id, case_id, and planner_owner_role are required")
        if self.recorded_at.tzinfo is None:
            raise ValueError("recorded_at must include a timezone")
        if not self.reason.strip():
            raise ValueError("decision reason is required")
        if self.outcome not in {"APPROVE", "DECLINE", "DEFER"}:
            raise ValueError("review decision outcome is invalid")

    def to_dict(self) -> dict[str, object]:
        return {
            "decision_id": self.decision_id,
            "case_id": self.case_id,
            "recorded_at": self.recorded_at.isoformat(),
            "planner_owner_role": self.planner_owner_role,
            "outcome": self.outcome,
            "reason": self.reason,
            "external_execution_permitted": self.external_execution_permitted,
        }


@dataclass(frozen=True)
class ReviewCaseSummary:
    """A reconstructed case summary; state is derived only from immutable events."""

    case: ReviewCase
    state: ReviewCaseState
    decisions: tuple[ReviewDecisionEvent, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            **self.case.to_dict(),
            "state": self.state,
            "decisions": [decision.to_dict() for decision in self.decisions],
        }
