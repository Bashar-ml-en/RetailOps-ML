"""One-time, post-selection final-test reporting for FreshRetailNet benchmarks."""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from math import sqrt
from pathlib import Path

from sklearn.metrics import mean_absolute_error, mean_squared_error

from app.agents.price_signal import ForecastEvaluationAgent
from app.schemas.benchmark import (
    FRESHRETAILNET_BENCHMARK_TENANT_ID,
    FreshRetailNetFinalTestReport,
    FinalTestScopeEvaluation,
)
from app.services.series import DemandSeriesError, DailyDemandSeries, build_daily_demand_series
from app.services.storage import SnapshotStore
from app.services.validation import CsvBundle


class FinalTestReportError(ValueError):
    """Raised when an immutable final test cannot be evaluated safely."""


class PublicBenchmarkFinalTestReporter:
    """Evaluate the validation-selected model once without modifying its registry record."""

    def __init__(
        self,
        store: SnapshotStore,
        agent: ForecastEvaluationAgent | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.store = store
        self.agent = agent or ForecastEvaluationAgent()
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    @classmethod
    def for_root(cls, root: Path) -> "PublicBenchmarkFinalTestReporter":
        return cls(store=SnapshotStore(root))

    def evaluate_and_persist(
        self, *, benchmark_run_id: str, baseline_run_id: str, model_run_id: str
    ) -> FreshRetailNetFinalTestReport:
        """Create the only final-test report for one recorded public model run."""

        report_id = f"final-test-{model_run_id}"
        if self.store.load_public_benchmark_final_test_report(report_id) is not None:
            raise FinalTestReportError("FINAL_TEST_REPORT_ALREADY_EXISTS")

        benchmark_run = self._required(self.store.load_public_benchmark_run(benchmark_run_id), "BENCHMARK_RUN_NOT_FOUND")
        baseline_run = self._required(self.store.load_baseline_run(baseline_run_id), "BASELINE_RUN_NOT_FOUND")
        model_run = self._required(self.store.load_model_run(model_run_id), "MODEL_RUN_NOT_FOUND")
        self._validate_record_chain(benchmark_run, baseline_run, model_run, baseline_run_id, model_run_id)

        snapshot = self._mapping(benchmark_run, "snapshot")
        bundle = self._load_snapshot_bundle(str(snapshot["snapshot_id"]), snapshot)
        try:
            build = build_daily_demand_series(
                bundle,
                operating_timezone="UTC",
                as_of=self._timestamp(str(snapshot["retrieved_at"])),
            )
        except DemandSeriesError as error:
            raise FinalTestReportError(f"FINAL_TEST_SERIES_INVALID:{error}") from error
        if build.feature_hash != model_run.get("feature_hash"):
            raise FinalTestReportError("FINAL_TEST_FEATURE_HASH_MISMATCH")

        evaluations = self._evaluate_selected_model(build.series, baseline_run, model_run)
        limitations = tuple(str(item) for item in model_run.get("limitations", ()))
        dataset = self._mapping(benchmark_run, "dataset")
        report = FreshRetailNetFinalTestReport(
            report_id=report_id,
            evaluated_at=self.clock(),
            benchmark_run_id=benchmark_run_id,
            baseline_run_id=baseline_run_id,
            model_run_id=model_run_id,
            snapshot_id=str(snapshot["snapshot_id"]),
            tenant_id=str(benchmark_run["tenant_id"]),
            source_revision=str(dataset["source_revision"]),
            source_file_sha256=self._optional_string(dataset.get("source_file_sha256")),
            selected_model_version=str(model_run["selected_model_version"]),
            selection=str(model_run["selection"]),  # type: ignore[arg-type]
            selection_rationale=str(model_run["selection_rationale"]),
            status=str(model_run["status"]),  # type: ignore[arg-type]
            evaluations=tuple(evaluations),
            macro_average_mae=sum(item.selected_model_mae for item in evaluations) / len(evaluations),
            macro_average_rmse=sum(item.selected_model_rmse for item in evaluations) / len(evaluations),
            limitations=limitations,
        )
        decision = self.agent.decide(report)
        report = FreshRetailNetFinalTestReport(
            **{
                **report.__dict__,
                "agent_decision": {
                    "agent": decision.agent,
                    "status": decision.status,
                    "findings": [
                        {"statement": finding.statement, "evidence_refs": list(finding.evidence_refs)}
                        for finding in decision.findings
                    ],
                    "limitations": list(decision.limitations),
                    "next_action": decision.next_action,
                },
            }
        )
        self.store.persist_public_benchmark_final_test_report(report)
        return report

    @staticmethod
    def _required(payload: dict[str, object] | None, error: str) -> dict[str, object]:
        if payload is None:
            raise FinalTestReportError(error)
        return payload

    @staticmethod
    def _mapping(payload: Mapping[str, object], key: str) -> dict[str, object]:
        value = payload.get(key)
        if not isinstance(value, dict):
            raise FinalTestReportError(f"FINAL_TEST_RECORD_MALFORMED:{key}")
        return value

    @staticmethod
    def _timestamp(value: str) -> datetime:
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError as error:
            raise FinalTestReportError("FINAL_TEST_RECORD_MALFORMED:retrieved_at") from error
        if parsed.tzinfo is None:
            raise FinalTestReportError("FINAL_TEST_RECORD_MALFORMED:retrieved_at")
        return parsed

    @staticmethod
    def _optional_string(value: object) -> str | None:
        return value if isinstance(value, str) else None

    def _validate_record_chain(
        self,
        benchmark_run: Mapping[str, object],
        baseline_run: Mapping[str, object],
        model_run: Mapping[str, object],
        baseline_run_id: str,
        model_run_id: str,
    ) -> None:
        snapshot = self._mapping(benchmark_run, "snapshot")
        data_contract = self._mapping(benchmark_run, "data_contract")
        if (
            benchmark_run.get("source_type") != "PUBLIC_BENCHMARK"
            or benchmark_run.get("data_classification") != "PUBLIC_BENCHMARK"
            or benchmark_run.get("tenant_id") != FRESHRETAILNET_BENCHMARK_TENANT_ID
        ):
            raise FinalTestReportError("PUBLIC_BENCHMARK_REQUIRED")
        if data_contract.get("status") not in {"PASS", "PASS_WITH_LIMITATIONS"}:
            raise FinalTestReportError("DATA_CONTRACT_NOT_ACCEPTED")
        approved_uses = data_contract.get("approved_uses")
        if not isinstance(approved_uses, list) or "demand_forecast" not in approved_uses:
            raise FinalTestReportError("DEMAND_FORECAST_NOT_APPROVED")
        snapshot_id = snapshot.get("snapshot_id")
        tenant_id = benchmark_run.get("tenant_id")
        if (
            baseline_run.get("run_id") != baseline_run_id
            or model_run.get("model_run_id") != model_run_id
            or baseline_run.get("snapshot_id") != snapshot_id
            or model_run.get("snapshot_id") != snapshot_id
            or baseline_run.get("tenant_id") != tenant_id
            or model_run.get("tenant_id") != tenant_id
            or model_run.get("baseline_run_id") != baseline_run_id
        ):
            raise FinalTestReportError("FINAL_TEST_ARTIFACT_CHAIN_MISMATCH")
        if model_run.get("status") not in {"PASS", "PASS_WITH_LIMITATIONS"}:
            raise FinalTestReportError("MODEL_RUN_NOT_ACCEPTED")
        if model_run.get("final_test_state") != "LOCKED_UNEVALUATED":
            raise FinalTestReportError("FINAL_TEST_NOT_LOCKED")
        if model_run.get("selection") not in {"PROMOTED_CANDIDATE", "RETAINED_BASELINE"}:
            raise FinalTestReportError("MODEL_SELECTION_NOT_FINAL")
        selected_model_version = model_run.get("selected_model_version")
        candidate = self._mapping(model_run, "candidate_configuration")
        if selected_model_version not in {model_run.get("baseline_version"), candidate.get("model_version")}:
            raise FinalTestReportError("SELECTED_MODEL_VERSION_INVALID")

    def _load_snapshot_bundle(
        self, snapshot_id: str, manifest: Mapping[str, object]
    ) -> CsvBundle:
        table_hashes = manifest.get("table_hashes")
        if not isinstance(table_hashes, dict):
            raise FinalTestReportError("FINAL_TEST_RECORD_MALFORMED:table_hashes")
        snapshot_root = self.store.snapshots_root / snapshot_id
        tables: dict[str, bytes] = {}
        for table, expected_hash in table_hashes.items():
            if not isinstance(table, str) or not isinstance(expected_hash, str):
                raise FinalTestReportError("FINAL_TEST_RECORD_MALFORMED:table_hashes")
            path = snapshot_root / f"{table}.csv"
            if not path.is_file():
                raise FinalTestReportError(f"FINAL_TEST_SNAPSHOT_TABLE_MISSING:{table}")
            payload = path.read_bytes()
            if hashlib.sha256(payload).hexdigest() != expected_hash:
                raise FinalTestReportError(f"FINAL_TEST_SNAPSHOT_TABLE_HASH_MISMATCH:{table}")
            tables[table] = payload
        return CsvBundle(tables=tables)

    def _evaluate_selected_model(
        self,
        series: tuple[DailyDemandSeries, ...],
        baseline_run: Mapping[str, object],
        model_run: Mapping[str, object],
    ) -> list[FinalTestScopeEvaluation]:
        baseline_evaluations = self._evaluations_by_scope(baseline_run, "baseline")
        model_evaluations = self._evaluations_by_scope(model_run, "model")
        series_by_scope = {item.scope_ref: item for item in series}
        if set(baseline_evaluations) != set(model_evaluations) or set(model_evaluations) != set(series_by_scope):
            raise FinalTestReportError("FINAL_TEST_SCOPE_MISMATCH")

        candidate = self._mapping(model_run, "candidate_configuration")
        selected_model_version = str(model_run["selected_model_version"])
        evaluations: list[FinalTestScopeEvaluation] = []
        for scope_ref in sorted(series_by_scope):
            baseline = baseline_evaluations[scope_ref]
            model = model_evaluations[scope_ref]
            daily_series = series_by_scope[scope_ref]
            self._validate_scope_split(baseline, model, daily_series)
            training_days = self._integer(baseline, "training_days")
            validation_days = self._integer(baseline, "validation_days")
            locked_test_days = self._integer(baseline, "locked_test_days")
            test_start = training_days + validation_days
            test_actuals = daily_series.quantities[test_start : test_start + locked_test_days]
            history = list(daily_series.quantities[:test_start])
            if selected_model_version == model_run.get("baseline_version"):
                predictions = self._baseline_predictions(history, test_actuals)
            elif selected_model_version == candidate.get("model_version"):
                predictions = self._candidate_predictions(history, test_actuals, candidate)
            else:  # Protected by _validate_record_chain; keep this path defensive.
                raise FinalTestReportError("SELECTED_MODEL_VERSION_INVALID")
            evaluations.append(
                FinalTestScopeEvaluation(
                    sku=str(baseline["sku"]),
                    location_id=str(baseline["location_id"]),
                    quantity_unit=str(baseline["quantity_unit"]),
                    locked_test_start=str(baseline["locked_test_start"]),
                    locked_test_end=str(baseline["locked_test_end"]),
                    locked_test_days=locked_test_days,
                    selected_model_mae=float(mean_absolute_error(test_actuals, predictions)),
                    selected_model_rmse=float(sqrt(mean_squared_error(test_actuals, predictions))),
                )
            )
        if not evaluations:
            raise FinalTestReportError("FINAL_TEST_NO_ELIGIBLE_SCOPE")
        return evaluations

    @staticmethod
    def _evaluations_by_scope(payload: Mapping[str, object], label: str) -> dict[str, dict[str, object]]:
        raw_evaluations = payload.get("evaluations")
        if not isinstance(raw_evaluations, list) or not raw_evaluations:
            raise FinalTestReportError(f"FINAL_TEST_RECORD_MALFORMED:{label}_evaluations")
        output: dict[str, dict[str, object]] = {}
        for evaluation in raw_evaluations:
            if not isinstance(evaluation, dict):
                raise FinalTestReportError(f"FINAL_TEST_RECORD_MALFORMED:{label}_evaluations")
            try:
                scope_ref = (
                    f"sku:{evaluation['sku']}|location:{evaluation['location_id']}|"
                    f"unit:{evaluation['quantity_unit']}"
                )
            except KeyError as error:
                raise FinalTestReportError(f"FINAL_TEST_RECORD_MALFORMED:{label}_evaluations") from error
            if scope_ref in output:
                raise FinalTestReportError(f"FINAL_TEST_RECORD_MALFORMED:{label}_evaluations")
            output[scope_ref] = evaluation
        return output

    def _validate_scope_split(
        self,
        baseline: Mapping[str, object],
        model: Mapping[str, object],
        series: DailyDemandSeries,
    ) -> None:
        for field in (
            "sku",
            "location_id",
            "quantity_unit",
            "training_days",
            "validation_days",
            "locked_test_days",
            "locked_test_start",
            "locked_test_end",
        ):
            if baseline.get(field) != model.get(field):
                raise FinalTestReportError("FINAL_TEST_SPLIT_MISMATCH")
        training_days = self._integer(baseline, "training_days")
        validation_days = self._integer(baseline, "validation_days")
        locked_test_days = self._integer(baseline, "locked_test_days")
        if len(series.dates) != training_days + validation_days + locked_test_days:
            raise FinalTestReportError("FINAL_TEST_SERIES_LENGTH_MISMATCH")
        if (
            series.dates[training_days + validation_days].isoformat() != baseline.get("locked_test_start")
            or series.dates[-1].isoformat() != baseline.get("locked_test_end")
        ):
            raise FinalTestReportError("FINAL_TEST_SPLIT_MISMATCH")

    @staticmethod
    def _integer(payload: Mapping[str, object], field: str) -> int:
        value = payload.get(field)
        if not isinstance(value, int) or value <= 0:
            raise FinalTestReportError(f"FINAL_TEST_RECORD_MALFORMED:{field}")
        return value

    @staticmethod
    def _baseline_predictions(history: list[float], actuals: tuple[float, ...]) -> list[float]:
        predictions: list[float] = []
        for actual in actuals:
            predictions.append(history[-1])
            history.append(actual)
        return predictions

    def _candidate_predictions(
        self, history: list[float], actuals: tuple[float, ...], candidate: Mapping[str, object]
    ) -> list[float]:
        window_days = self._integer(candidate, "window_days")
        if candidate.get("algorithm") != "trailing_observed_daily_mean":
            raise FinalTestReportError("FINAL_TEST_CANDIDATE_CONFIGURATION_UNSUPPORTED")
        predictions: list[float] = []
        for actual in actuals:
            observed_window = history[-window_days:]
            predictions.append(sum(observed_window) / len(observed_window))
            history.append(actual)
        return predictions
