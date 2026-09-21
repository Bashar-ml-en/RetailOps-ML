"""Typed, reproducible artifacts for chronological forecast evaluation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


EvaluationStatus = Literal["PASS", "PASS_WITH_LIMITATIONS", "REJECT", "INCONCLUSIVE"]
ModelSelection = Literal["PROMOTED_CANDIDATE", "RETAINED_BASELINE", "NOT_EVALUATED"]


@dataclass(frozen=True)
class BaselineRunRequest:
    """Declared evaluation policy for one approved snapshot."""

    tenant_id: str
    snapshot_id: str
    operating_timezone: str
    minimum_training_days: int = 14
    validation_days: int = 7
    locked_test_days: int = 7

    def __post_init__(self) -> None:
        if not self.tenant_id.strip() or not self.snapshot_id.strip():
            raise ValueError("tenant_id and snapshot_id are required")
        if min(self.minimum_training_days, self.validation_days, self.locked_test_days) <= 0:
            raise ValueError("baseline split lengths must be positive")
        try:
            ZoneInfo(self.operating_timezone)
        except ZoneInfoNotFoundError as error:
            raise ValueError("operating_timezone must be an IANA timezone") from error


@dataclass(frozen=True)
class BaselineScopeEvaluation:
    """Validation-only result for one compatible SKU-location-unit demand series."""

    sku: str
    location_id: str
    quantity_unit: str
    history_start: date
    training_end: date
    validation_start: date
    validation_end: date
    locked_test_start: date
    locked_test_end: date
    training_days: int
    validation_days: int
    locked_test_days: int
    validation_mae: float
    validation_rmse: float

    def to_dict(self) -> dict[str, object]:
        return {
            "sku": self.sku,
            "location_id": self.location_id,
            "quantity_unit": self.quantity_unit,
            "history_start": self.history_start.isoformat(),
            "training_end": self.training_end.isoformat(),
            "validation_start": self.validation_start.isoformat(),
            "validation_end": self.validation_end.isoformat(),
            "locked_test_start": self.locked_test_start.isoformat(),
            "locked_test_end": self.locked_test_end.isoformat(),
            "training_days": self.training_days,
            "validation_days": self.validation_days,
            "locked_test_days": self.locked_test_days,
            "validation_mae": self.validation_mae,
            "validation_rmse": self.validation_rmse,
            "final_test_state": "LOCKED_UNEVALUATED",
        }


@dataclass(frozen=True)
class BaselineRun:
    """Registered baseline evaluation; no ML candidate or production score."""

    run_id: str
    request: BaselineRunRequest
    status: EvaluationStatus
    feature_version: str
    feature_hash: str | None
    baseline_version: str
    evaluations: tuple[BaselineScopeEvaluation, ...] = field(default_factory=tuple)
    limitations: tuple[str, ...] = field(default_factory=tuple)
    next_action: str = "stop"
    agent_decision: dict[str, object] | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "run_id": self.run_id,
            "tenant_id": self.request.tenant_id,
            "snapshot_id": self.request.snapshot_id,
            "operating_timezone": self.request.operating_timezone,
            "status": self.status,
            "feature_version": self.feature_version,
            "feature_hash": self.feature_hash,
            "baseline_version": self.baseline_version,
            "split_policy": {
                "minimum_training_days": self.request.minimum_training_days,
                "validation_days": self.request.validation_days,
                "locked_test_days": self.request.locked_test_days,
            },
            "evaluations": [evaluation.to_dict() for evaluation in self.evaluations],
            "limitations": list(self.limitations),
            "next_action": self.next_action,
            "agent_decision": self.agent_decision,
        }


@dataclass(frozen=True)
class ModelLifecycleRequest:
    """Declared context for one fixed-candidate comparison against a baseline."""

    tenant_id: str
    snapshot_id: str
    baseline_run_id: str

    def __post_init__(self) -> None:
        if not all(value.strip() for value in (self.tenant_id, self.snapshot_id, self.baseline_run_id)):
            raise ValueError("tenant_id, snapshot_id, and baseline_run_id are required")


@dataclass(frozen=True)
class CandidateModelConfiguration:
    """Versioned, fixed configuration for the only local lifecycle candidate."""

    model_version: str
    algorithm: str
    window_days: int
    prediction_rule: str
    feature_version: str

    def to_dict(self) -> dict[str, object]:
        return {
            "model_version": self.model_version,
            "algorithm": self.algorithm,
            "window_days": self.window_days,
            "prediction_rule": self.prediction_rule,
            "feature_version": self.feature_version,
        }


@dataclass(frozen=True)
class CandidateScopeEvaluation:
    """Validation-only baseline/candidate comparison for one compatible scope."""

    sku: str
    location_id: str
    quantity_unit: str
    history_start: date
    training_end: date
    validation_start: date
    validation_end: date
    locked_test_start: date
    locked_test_end: date
    training_days: int
    validation_days: int
    locked_test_days: int
    baseline_validation_mae: float
    baseline_validation_rmse: float
    candidate_validation_mae: float
    candidate_validation_rmse: float

    @property
    def scope_ref(self) -> str:
        return f"sku:{self.sku}|location:{self.location_id}|unit:{self.quantity_unit}"

    def to_dict(self) -> dict[str, object]:
        return {
            "sku": self.sku,
            "location_id": self.location_id,
            "quantity_unit": self.quantity_unit,
            "history_start": self.history_start.isoformat(),
            "training_end": self.training_end.isoformat(),
            "validation_start": self.validation_start.isoformat(),
            "validation_end": self.validation_end.isoformat(),
            "locked_test_start": self.locked_test_start.isoformat(),
            "locked_test_end": self.locked_test_end.isoformat(),
            "training_days": self.training_days,
            "validation_days": self.validation_days,
            "locked_test_days": self.locked_test_days,
            "baseline_validation_mae": self.baseline_validation_mae,
            "baseline_validation_rmse": self.baseline_validation_rmse,
            "candidate_validation_mae": self.candidate_validation_mae,
            "candidate_validation_rmse": self.candidate_validation_rmse,
            "final_test_state": "LOCKED_UNEVALUATED",
        }


@dataclass(frozen=True)
class ModelLifecycleRun:
    """Local registry-ready result for a fixed candidate-model comparison.

    This is an evaluation and selection artifact, not a deployed model or a
    production score. The final test partition stays unavailable to selection.
    """

    model_run_id: str
    evaluated_at: datetime
    request: ModelLifecycleRequest
    status: EvaluationStatus
    registry_schema_version: str
    feature_version: str
    feature_hash: str | None
    baseline_version: str
    candidate_configuration: CandidateModelConfiguration
    evaluations: tuple[CandidateScopeEvaluation, ...] = field(default_factory=tuple)
    selection: ModelSelection = "NOT_EVALUATED"
    selected_model_version: str | None = None
    selection_rationale: str = "not_evaluated"
    rollback_baseline_version: str | None = None
    rollback_baseline_run_id: str | None = None
    limitations: tuple[str, ...] = field(default_factory=tuple)
    next_action: str = "stop"
    agent_decision: dict[str, object] | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "registry_schema_version": self.registry_schema_version,
            "model_run_id": self.model_run_id,
            "evaluated_at": self.evaluated_at.isoformat(),
            "tenant_id": self.request.tenant_id,
            "snapshot_id": self.request.snapshot_id,
            "baseline_run_id": self.request.baseline_run_id,
            "status": self.status,
            "feature_version": self.feature_version,
            "feature_hash": self.feature_hash,
            "baseline_version": self.baseline_version,
            "candidate_configuration": self.candidate_configuration.to_dict(),
            "evaluations": [evaluation.to_dict() for evaluation in self.evaluations],
            "selection": self.selection,
            "selected_model_version": self.selected_model_version,
            "selection_rationale": self.selection_rationale,
            "rollback_baseline": {
                "model_version": self.rollback_baseline_version,
                "baseline_run_id": self.rollback_baseline_run_id,
            },
            "final_test_state": "LOCKED_UNEVALUATED",
            "limitations": list(self.limitations),
            "next_action": self.next_action,
            "agent_decision": self.agent_decision,
        }
