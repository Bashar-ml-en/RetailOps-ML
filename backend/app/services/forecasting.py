"""Chronology-safe naïve demand baseline evaluation."""

from __future__ import annotations

from dataclasses import replace
from math import sqrt
from uuid import uuid4

from sklearn.metrics import mean_absolute_error, mean_squared_error

from app.agents.price_signal import ForecastEvaluationAgent
from app.schemas.connector import DataContractResult, SnapshotManifest
from app.schemas.forecast import BaselineRun, BaselineRunRequest, BaselineScopeEvaluation
from app.services.series import DemandSeriesError, DailyDemandSeries, build_daily_demand_series
from app.services.validation import CsvBundle


FEATURE_VERSION = "daily-demand-v1"
BASELINE_VERSION = "naive-last-observation-v1"


class BaselineRunner:
    """Evaluate a rolling naïve baseline without ever touching the final test days."""

    def __init__(self, agent: ForecastEvaluationAgent | None = None) -> None:
        self.agent = agent or ForecastEvaluationAgent()

    def run(
        self,
        request: BaselineRunRequest,
        *,
        manifest: SnapshotManifest,
        data_contract: DataContractResult,
        bundle: CsvBundle,
    ) -> BaselineRun:
        run_id = str(uuid4())
        rejected = self._input_rejection(run_id, request, manifest, data_contract)
        if rejected is not None:
            return self._with_agent(rejected)

        contract_limitations = data_contract.limitations

        try:
            build = build_daily_demand_series(
                bundle,
                operating_timezone=request.operating_timezone,
                as_of=manifest.retrieved_at,
            )
        except DemandSeriesError as error:
            status = "REJECT" if str(error) in {"FUTURE_ORDER_OBSERVATION", "UNMAPPED_DEMAND_UNIT"} else "INCONCLUSIVE"
            return self._with_agent(
                BaselineRun(
                    run_id=run_id,
                    request=request,
                    status=status,
                    feature_version=FEATURE_VERSION,
                    feature_hash=None,
                    baseline_version=BASELINE_VERSION,
                    limitations=(*contract_limitations, str(error)),
                    next_action="correct_snapshot" if status == "REJECT" else "request_eligible_history",
                )
            )

        evaluations: list[BaselineScopeEvaluation] = []
        limitations: list[str] = []
        required_days = request.minimum_training_days + request.validation_days + request.locked_test_days
        for series in build.series:
            if len(series.dates) < required_days:
                limitations.append(f"INSUFFICIENT_HISTORY:{series.scope_ref}")
                continue
            evaluations.append(self._evaluate_scope(series, request))

        if not evaluations:
            run = BaselineRun(
                run_id=run_id,
                request=request,
                status="INCONCLUSIVE",
                feature_version=FEATURE_VERSION,
                feature_hash=build.feature_hash,
                baseline_version=BASELINE_VERSION,
                limitations=(*contract_limitations, *tuple(limitations))
                or ("NO_ELIGIBLE_DEMAND_SCOPE",),
                next_action="request_eligible_history",
            )
        else:
            run = BaselineRun(
                run_id=run_id,
                request=request,
                status="PASS_WITH_LIMITATIONS" if (limitations or contract_limitations) else "PASS",
                feature_version=FEATURE_VERSION,
                feature_hash=build.feature_hash,
                baseline_version=BASELINE_VERSION,
                evaluations=tuple(evaluations),
                limitations=(*contract_limitations, *tuple(limitations)),
                next_action="register_baseline",
            )
        return self._with_agent(run)

    @staticmethod
    def _input_rejection(
        run_id: str,
        request: BaselineRunRequest,
        manifest: SnapshotManifest,
        data_contract: DataContractResult,
    ) -> BaselineRun | None:
        if request.tenant_id != manifest.tenant_id or request.snapshot_id != manifest.snapshot_id:
            return BaselineRun(
                run_id=run_id,
                request=request,
                status="REJECT",
                feature_version=FEATURE_VERSION,
                feature_hash=None,
                baseline_version=BASELINE_VERSION,
                limitations=("SNAPSHOT_SCOPE_MISMATCH",),
                next_action="correct_snapshot_scope",
            )
        if data_contract.status not in {"PASS", "PASS_WITH_LIMITATIONS"}:
            return BaselineRun(
                run_id=run_id,
                request=request,
                status="REJECT" if data_contract.status == "REJECT" else "INCONCLUSIVE",
                feature_version=FEATURE_VERSION,
                feature_hash=None,
                baseline_version=BASELINE_VERSION,
                limitations=("DATA_CONTRACT_NOT_ACCEPTED", *data_contract.limitations),
                next_action=(
                    "correct_connector_mapping"
                    if data_contract.status == "REJECT"
                    else "request_eligible_history"
                ),
            )
        if "demand_forecast" not in data_contract.approved_uses:
            return BaselineRun(
                run_id=run_id,
                request=request,
                status="INCONCLUSIVE",
                feature_version=FEATURE_VERSION,
                feature_hash=None,
                baseline_version=BASELINE_VERSION,
                limitations=("DEMAND_FORECAST_NOT_APPROVED", *data_contract.limitations),
                next_action="request_eligible_history",
            )
        return None

    @staticmethod
    def _evaluate_scope(
        series: DailyDemandSeries, request: BaselineRunRequest
    ) -> BaselineScopeEvaluation:
        training_days = len(series.dates) - request.validation_days - request.locked_test_days
        validation_start = training_days
        validation_end = validation_start + request.validation_days
        validation_actuals = series.quantities[validation_start:validation_end]
        history = list(series.quantities[:training_days])
        predictions: list[float] = []
        for actual in validation_actuals:
            predictions.append(history[-1])
            history.append(actual)

        return BaselineScopeEvaluation(
            sku=series.sku,
            location_id=series.location_id,
            quantity_unit=series.quantity_unit,
            history_start=series.dates[0],
            training_end=series.dates[training_days - 1],
            validation_start=series.dates[validation_start],
            validation_end=series.dates[validation_end - 1],
            locked_test_start=series.dates[validation_end],
            locked_test_end=series.dates[-1],
            training_days=training_days,
            validation_days=request.validation_days,
            locked_test_days=request.locked_test_days,
            validation_mae=float(mean_absolute_error(validation_actuals, predictions)),
            validation_rmse=float(sqrt(mean_squared_error(validation_actuals, predictions))),
        )

    def _with_agent(self, run: BaselineRun) -> BaselineRun:
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
