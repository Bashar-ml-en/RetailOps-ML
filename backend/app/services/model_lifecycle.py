"""Deterministic, chronology-safe fixed-candidate model lifecycle.

The local lifecycle compares exactly one predeclared trailing-mean candidate
with the recorded naïve baseline without using locked test days for selection.
It is not a trainer, scoring service, or production deployment path.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from math import isclose, sqrt
from uuid import uuid4

from sklearn.metrics import mean_absolute_error, mean_squared_error

from app.agents.price_signal import ForecastEvaluationAgent
from app.schemas.connector import DataContractResult, SnapshotManifest
from app.schemas.forecast import (
    BaselineRun,
    BaselineScopeEvaluation,
    CandidateModelConfiguration,
    CandidateScopeEvaluation,
    ModelLifecycleRequest,
    ModelLifecycleRun,
)
from app.services.forecasting import BASELINE_VERSION, FEATURE_VERSION, BaselineRunner
from app.services.series import DemandSeriesError, DailyDemandSeries, build_daily_demand_series
from app.services.validation import CsvBundle


MODEL_REGISTRY_SCHEMA_VERSION = "local-model-registry-v1"
CANDIDATE_VERSION = "trailing-mean-7-v1"
CANDIDATE_CONFIGURATION = CandidateModelConfiguration(
    model_version=CANDIDATE_VERSION,
    algorithm="trailing_observed_daily_mean",
    window_days=7,
    prediction_rule=(
        "Predict each validation day from only the preceding seven observed daily demands; "
        "append that day's actual only after its prediction."
    ),
    feature_version=FEATURE_VERSION,
)


class ModelLifecycleRunner:
    """Register a fixed candidate selection without using locked test days."""

    def __init__(self, agent: ForecastEvaluationAgent | None = None) -> None:
        self.agent = agent or ForecastEvaluationAgent()

    def run(
        self,
        request: ModelLifecycleRequest,
        *,
        manifest: SnapshotManifest,
        data_contract: DataContractResult,
        baseline_run: BaselineRun,
        bundle: CsvBundle,
    ) -> ModelLifecycleRun:
        model_run_id = str(uuid4())
        rejected = self._input_rejection(
            model_run_id, request, manifest, data_contract, baseline_run
        )
        if rejected is not None:
            return self._with_agent(rejected)

        try:
            build = build_daily_demand_series(
                bundle,
                operating_timezone=baseline_run.request.operating_timezone,
                as_of=manifest.retrieved_at,
            )
        except DemandSeriesError as error:
            status = "REJECT" if str(error) in {"FUTURE_ORDER_OBSERVATION", "UNMAPPED_DEMAND_UNIT"} else "INCONCLUSIVE"
            return self._with_agent(
                self._not_evaluated(
                    model_run_id,
                    request,
                    baseline_run,
                    status=status,
                    limitations=(str(error),),
                    next_action="correct_snapshot" if status == "REJECT" else "request_eligible_history",
                )
            )

        if baseline_run.feature_version != FEATURE_VERSION:
            return self._with_agent(
                self._not_evaluated(
                    model_run_id,
                    request,
                    baseline_run,
                    status="REJECT",
                    limitations=("FEATURE_VERSION_MISMATCH",),
                    next_action="rebuild_baseline",
                    feature_hash=build.feature_hash,
                )
            )
        if baseline_run.feature_hash != build.feature_hash:
            return self._with_agent(
                self._not_evaluated(
                    model_run_id,
                    request,
                    baseline_run,
                    status="REJECT",
                    limitations=("FEATURE_HASH_MISMATCH",),
                    next_action="rebuild_baseline",
                    feature_hash=build.feature_hash,
                )
            )

        try:
            evaluations = self._evaluate_scopes(build.series, baseline_run)
        except ModelLifecycleError as error:
            return self._with_agent(
                self._not_evaluated(
                    model_run_id,
                    request,
                    baseline_run,
                    status="REJECT",
                    limitations=(str(error),),
                    next_action="rebuild_baseline",
                    feature_hash=build.feature_hash,
                )
            )

        if all(
            evaluation.candidate_validation_mae < evaluation.baseline_validation_mae
            for evaluation in evaluations
        ):
            selection = "PROMOTED_CANDIDATE"
            selected_model_version = CANDIDATE_VERSION
            selection_rationale = "candidate_strictly_improves_validation_mae_for_every_eligible_scope"
            next_action = "register_local_candidate_champion"
        else:
            selection = "RETAINED_BASELINE"
            selected_model_version = baseline_run.baseline_version
            selection_rationale = "candidate_tied_or_regressed_validation_mae_for_at_least_one_eligible_scope"
            next_action = "retain_registered_baseline"

        return self._with_agent(
            ModelLifecycleRun(
                model_run_id=model_run_id,
                evaluated_at=datetime.now(timezone.utc),
                request=request,
                status=baseline_run.status,
                registry_schema_version=MODEL_REGISTRY_SCHEMA_VERSION,
                feature_version=FEATURE_VERSION,
                feature_hash=build.feature_hash,
                baseline_version=baseline_run.baseline_version,
                candidate_configuration=CANDIDATE_CONFIGURATION,
                evaluations=tuple(evaluations),
                selection=selection,
                selected_model_version=selected_model_version,
                selection_rationale=selection_rationale,
                rollback_baseline_version=baseline_run.baseline_version,
                rollback_baseline_run_id=baseline_run.run_id,
                limitations=baseline_run.limitations,
                next_action=next_action,
            )
        )

    @staticmethod
    def _input_rejection(
        model_run_id: str,
        request: ModelLifecycleRequest,
        manifest: SnapshotManifest,
        data_contract: DataContractResult,
        baseline_run: BaselineRun,
    ) -> ModelLifecycleRun | None:
        if request.tenant_id != manifest.tenant_id or request.snapshot_id != manifest.snapshot_id:
            return ModelLifecycleRunner._not_evaluated(
                model_run_id,
                request,
                baseline_run,
                status="REJECT",
                limitations=("SNAPSHOT_SCOPE_MISMATCH",),
                next_action="correct_snapshot_scope",
            )
        if data_contract.status not in {"PASS", "PASS_WITH_LIMITATIONS"}:
            return ModelLifecycleRunner._not_evaluated(
                model_run_id,
                request,
                baseline_run,
                status="REJECT" if data_contract.status == "REJECT" else "INCONCLUSIVE",
                limitations=("DATA_CONTRACT_NOT_ACCEPTED", *data_contract.limitations),
                next_action=(
                    "correct_connector_mapping"
                    if data_contract.status == "REJECT"
                    else "request_eligible_history"
                ),
            )
        if "demand_forecast" not in data_contract.approved_uses:
            return ModelLifecycleRunner._not_evaluated(
                model_run_id,
                request,
                baseline_run,
                status="INCONCLUSIVE",
                limitations=("DEMAND_FORECAST_NOT_APPROVED", *data_contract.limitations),
                next_action="request_eligible_history",
            )
        if baseline_run.run_id != request.baseline_run_id:
            return ModelLifecycleRunner._not_evaluated(
                model_run_id,
                request,
                baseline_run,
                status="REJECT",
                limitations=("BASELINE_RUN_MISMATCH",),
                next_action="select_matching_baseline",
            )
        if (
            baseline_run.request.tenant_id != request.tenant_id
            or baseline_run.request.snapshot_id != request.snapshot_id
        ):
            return ModelLifecycleRunner._not_evaluated(
                model_run_id,
                request,
                baseline_run,
                status="REJECT",
                limitations=("BASELINE_SCOPE_MISMATCH",),
                next_action="select_matching_baseline",
            )
        if baseline_run.status not in {"PASS", "PASS_WITH_LIMITATIONS"}:
            return ModelLifecycleRunner._not_evaluated(
                model_run_id,
                request,
                baseline_run,
                status="INCONCLUSIVE",
                limitations=("BASELINE_NOT_ACCEPTED", *baseline_run.limitations),
                next_action="request_eligible_history",
            )
        if baseline_run.baseline_version != BASELINE_VERSION:
            return ModelLifecycleRunner._not_evaluated(
                model_run_id,
                request,
                baseline_run,
                status="REJECT",
                limitations=("BASELINE_VERSION_MISMATCH",),
                next_action="rebuild_baseline",
            )
        return None

    @staticmethod
    def _evaluate_scopes(
        series: tuple[DailyDemandSeries, ...], baseline_run: BaselineRun
    ) -> list[CandidateScopeEvaluation]:
        baseline_by_scope = {
            ModelLifecycleRunner._baseline_scope_ref(evaluation): evaluation
            for evaluation in baseline_run.evaluations
        }
        if not baseline_by_scope:
            raise ModelLifecycleError("NO_REGISTERED_BASELINE_EVALUATIONS")

        series_by_scope = {item.scope_ref: item for item in series}
        if baseline_by_scope.keys() - series_by_scope.keys():
            raise ModelLifecycleError("BASELINE_SCOPE_MISMATCH")

        evaluations: list[CandidateScopeEvaluation] = []
        for scope_ref in sorted(baseline_by_scope):
            recorded_baseline = baseline_by_scope[scope_ref]
            daily_series = series_by_scope[scope_ref]
            recomputed_baseline = BaselineRunner._evaluate_scope(daily_series, baseline_run.request)
            if not ModelLifecycleRunner._baseline_matches(recorded_baseline, recomputed_baseline):
                raise ModelLifecycleError("BASELINE_METRIC_OR_SPLIT_MISMATCH")
            evaluations.append(
                ModelLifecycleRunner._evaluate_candidate(daily_series, recorded_baseline)
            )
        return evaluations

    @staticmethod
    def _evaluate_candidate(
        series: DailyDemandSeries, baseline: BaselineScopeEvaluation
    ) -> CandidateScopeEvaluation:
        training_days = baseline.training_days
        validation_end = training_days + baseline.validation_days
        history = list(series.quantities[:training_days])
        validation_actuals = series.quantities[training_days:validation_end]
        predictions: list[float] = []
        for actual in validation_actuals:
            observed_window = history[-CANDIDATE_CONFIGURATION.window_days :]
            predictions.append(sum(observed_window) / len(observed_window))
            history.append(actual)

        return CandidateScopeEvaluation(
            sku=baseline.sku,
            location_id=baseline.location_id,
            quantity_unit=baseline.quantity_unit,
            history_start=baseline.history_start,
            training_end=baseline.training_end,
            validation_start=baseline.validation_start,
            validation_end=baseline.validation_end,
            locked_test_start=baseline.locked_test_start,
            locked_test_end=baseline.locked_test_end,
            training_days=baseline.training_days,
            validation_days=baseline.validation_days,
            locked_test_days=baseline.locked_test_days,
            baseline_validation_mae=baseline.validation_mae,
            baseline_validation_rmse=baseline.validation_rmse,
            candidate_validation_mae=float(mean_absolute_error(validation_actuals, predictions)),
            candidate_validation_rmse=float(sqrt(mean_squared_error(validation_actuals, predictions))),
        )

    @staticmethod
    def _baseline_scope_ref(evaluation: BaselineScopeEvaluation) -> str:
        return f"sku:{evaluation.sku}|location:{evaluation.location_id}|unit:{evaluation.quantity_unit}"

    @staticmethod
    def _baseline_matches(
        recorded: BaselineScopeEvaluation, recomputed: BaselineScopeEvaluation
    ) -> bool:
        return (
            recorded.sku == recomputed.sku
            and recorded.location_id == recomputed.location_id
            and recorded.quantity_unit == recomputed.quantity_unit
            and recorded.history_start == recomputed.history_start
            and recorded.training_end == recomputed.training_end
            and recorded.validation_start == recomputed.validation_start
            and recorded.validation_end == recomputed.validation_end
            and recorded.locked_test_start == recomputed.locked_test_start
            and recorded.locked_test_end == recomputed.locked_test_end
            and recorded.training_days == recomputed.training_days
            and recorded.validation_days == recomputed.validation_days
            and recorded.locked_test_days == recomputed.locked_test_days
            and isclose(recorded.validation_mae, recomputed.validation_mae, abs_tol=1e-12)
            and isclose(recorded.validation_rmse, recomputed.validation_rmse, abs_tol=1e-12)
        )

    @staticmethod
    def _not_evaluated(
        model_run_id: str,
        request: ModelLifecycleRequest,
        baseline_run: BaselineRun,
        *,
        status: str,
        limitations: tuple[str, ...],
        next_action: str,
        feature_hash: str | None = None,
    ) -> ModelLifecycleRun:
        return ModelLifecycleRun(
            model_run_id=model_run_id,
            evaluated_at=datetime.now(timezone.utc),
            request=request,
            status=status,  # type: ignore[arg-type]
            registry_schema_version=MODEL_REGISTRY_SCHEMA_VERSION,
            feature_version=FEATURE_VERSION,
            feature_hash=feature_hash,
            baseline_version=baseline_run.baseline_version,
            candidate_configuration=CANDIDATE_CONFIGURATION,
            rollback_baseline_version=baseline_run.baseline_version,
            rollback_baseline_run_id=baseline_run.run_id,
            limitations=limitations,
            next_action=next_action,
        )

    def _with_agent(self, run: ModelLifecycleRun) -> ModelLifecycleRun:
        decision = self.agent.decide(run)
        return replace(
            run,
            agent_decision={
                "agent": decision.agent,
                "status": decision.status,
                "findings": [
                    {"statement": finding.statement, "evidence_refs": list(finding.evidence_refs)}
                    for finding in decision.findings
                ],
                "limitations": list(decision.limitations),
                "next_action": decision.next_action,
            },
        )


class ModelLifecycleError(ValueError):
    """Raised when a recorded baseline cannot be safely reused."""
