"""Persisted, fixture-only specialist workflow events for the local review path."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

from app.agents.contracts import DecisionStatus
from app.schemas.review import InventoryRiskRequest


WorkflowEventName = Literal[
    "QUEUED",
    "VALIDATING",
    "DATA_CONTRACT_REVIEWED",
    "FORECAST_EVALUATION_REVIEWED",
    "FEATURES_READY",
    "INVENTORY_RISK_REVIEWED",
    "IMPACT_RANKING_REVIEWED",
    "POLICY_CRITIC_REVIEWED",
    "ACTION_DRAFTED",
    "REVIEW_READY",
    "REJECTED",
    "INCONCLUSIVE",
    "FAILED",
]
WorkflowStatus = Literal["REVIEW_READY", "REJECTED", "INCONCLUSIVE", "FAILED"]


@dataclass(frozen=True)
class FixtureReviewWorkflowRequest:
    """Declared inputs for one local fixture run; no customer data is allowed."""

    data_classification: Literal["FIXTURE"]
    data_contract_status: DecisionStatus
    forecast_evaluation_status: DecisionStatus
    inventory_risk_request: InventoryRiskRequest
    planner_owner_role: str

    def __post_init__(self) -> None:
        if not self.planner_owner_role.strip():
            raise ValueError("planner_owner_role is required")


@dataclass(frozen=True)
class WorkflowEvent:
    """A stored transition backed by an actual typed artifact or safety result."""

    sequence: int
    name: WorkflowEventName
    occurred_at: datetime
    detail: str
    evidence_refs: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.sequence <= 0:
            raise ValueError("workflow event sequence must be positive")
        if self.occurred_at.tzinfo is None:
            raise ValueError("workflow event occurred_at must include a timezone")

    def to_dict(self) -> dict[str, object]:
        return {
            "sequence": self.sequence,
            "name": self.name,
            "occurred_at": self.occurred_at.isoformat(),
            "detail": self.detail,
            "evidence_refs": list(self.evidence_refs),
            "limitations": list(self.limitations),
        }


@dataclass(frozen=True)
class FixtureReviewWorkflowRun:
    """Immutable local workflow record; it has no production-worker semantics."""

    workflow_run_id: str
    created_at: datetime
    data_classification: Literal["FIXTURE"]
    snapshot_id: str
    status: WorkflowStatus
    events: tuple[WorkflowEvent, ...]
    review_case_id: str | None = None
    limitations: tuple[str, ...] = field(default_factory=tuple)
    run_schema_version: Literal["fixture-review-workflow-run-v1"] = (
        "fixture-review-workflow-run-v1"
    )

    def __post_init__(self) -> None:
        if not self.workflow_run_id.strip() or not self.snapshot_id.strip():
            raise ValueError("workflow_run_id and snapshot_id are required")
        if self.created_at.tzinfo is None:
            raise ValueError("created_at must include a timezone")
        if not self.events:
            raise ValueError("workflow events are required")
        terminal = self.events[-1].name
        expected_terminal = {
            "REVIEW_READY": "REVIEW_READY",
            "REJECTED": "REJECTED",
            "INCONCLUSIVE": "INCONCLUSIVE",
            "FAILED": "FAILED",
        }[self.status]
        if terminal != expected_terminal:
            raise ValueError("workflow status must match the persisted terminal event")
        if self.status == "REVIEW_READY" and not self.review_case_id:
            raise ValueError("review-ready workflow requires a review_case_id")
        if self.status != "REVIEW_READY" and self.review_case_id is not None:
            raise ValueError("terminal non-review workflow cannot contain a review_case_id")

    def to_dict(self) -> dict[str, object]:
        return {
            "run_schema_version": self.run_schema_version,
            "workflow_run_id": self.workflow_run_id,
            "created_at": self.created_at.isoformat(),
            "data_classification": self.data_classification,
            "snapshot_id": self.snapshot_id,
            "status": self.status,
            "review_case_id": self.review_case_id,
            "events": [event.to_dict() for event in self.events],
            "limitations": list(self.limitations),
            "external_execution_permitted": False,
        }
