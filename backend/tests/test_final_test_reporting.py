"""Tests for the one-time, post-selection public benchmark final-test report."""

from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

from app.schemas.benchmark import (
    FRESHRETAILNET_BENCHMARK_TENANT_ID,
    FreshRetailNetBenchmarkRequest,
    FreshRetailNetScope,
)
from app.schemas.forecast import BaselineRunRequest, ModelLifecycleRequest
from app.services.final_test import FinalTestReportError, PublicBenchmarkFinalTestReporter
from app.services.forecasting import BaselineRunner
from app.services.freshretailnet import FreshRetailNetBenchmarkRunner
from app.services.model_lifecycle import ModelLifecycleRunner
from app.services.storage import SnapshotStore


AS_OF = datetime(2026, 2, 1, tzinfo=timezone.utc)


def request() -> FreshRetailNetBenchmarkRequest:
    return FreshRetailNetBenchmarkRequest(
        selection_id="frn-final-test-fixture",
        scopes=tuple(FreshRetailNetScope(store_id=101, product_id=index) for index in range(20)),
        as_of=AS_OF,
    )


def source_frame(*, locked_test_value: float = 5.0) -> pd.DataFrame:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    rows: list[dict[str, object]] = []
    for product_id in range(20):
        for offset in range(28):
            rows.append(
                {
                    "city_id": 9,
                    "store_id": 101,
                    "management_group_id": 1,
                    "first_category_id": 2,
                    "second_category_id": 3,
                    "third_category_id": 4,
                    "product_id": product_id,
                    "dt": (start + timedelta(days=offset)).date().isoformat(),
                    "sale_amount": locked_test_value if offset >= 21 else 1.0,
                    "hours_sale": "[]",
                    "stock_hour6_22_cnt": 0,
                    "hours_stock_status": "[]",
                    "discount": 1.0,
                    "holiday_flag": 0,
                    "activity_flag": 0,
                    "precpt": 0.0,
                    "avg_temperature": 20.0,
                    "avg_humidity": 0.5,
                    "avg_wind_level": 1.0,
                }
            )
    return pd.DataFrame(rows)


def recorded_lifecycle(tmp_path, *, locked_test_value: float = 5.0):
    store = SnapshotStore(tmp_path)
    materialization = FreshRetailNetBenchmarkRunner.for_root(tmp_path).run(
        request(), source_frame(locked_test_value=locked_test_value)
    )
    baseline = BaselineRunner().run(
        BaselineRunRequest(
            tenant_id=FRESHRETAILNET_BENCHMARK_TENANT_ID,
            snapshot_id=materialization.run.manifest.snapshot_id,
            operating_timezone="UTC",
        ),
        manifest=materialization.run.manifest,
        data_contract=materialization.run.result,
        bundle=materialization.bundle,
    )
    store.persist_baseline_run(baseline)
    lifecycle = ModelLifecycleRunner().run(
        ModelLifecycleRequest(
            tenant_id=FRESHRETAILNET_BENCHMARK_TENANT_ID,
            snapshot_id=materialization.run.manifest.snapshot_id,
            baseline_run_id=baseline.run_id,
        ),
        manifest=materialization.run.manifest,
        data_contract=materialization.run.result,
        baseline_run=baseline,
        bundle=materialization.bundle,
    )
    store.persist_model_run(lifecycle)
    return materialization.run, baseline, lifecycle


def test_final_test_report_evaluates_selected_model_once_without_changing_selection(tmp_path) -> None:
    benchmark, baseline, lifecycle = recorded_lifecycle(tmp_path)
    assert lifecycle.selection == "RETAINED_BASELINE"

    report = PublicBenchmarkFinalTestReporter.for_root(tmp_path).evaluate_and_persist(
        benchmark_run_id=benchmark.run_id,
        baseline_run_id=baseline.run_id,
        model_run_id=lifecycle.model_run_id,
    )

    assert report.status == "PASS_WITH_LIMITATIONS"
    assert report.selection == "RETAINED_BASELINE"
    assert report.selected_model_version == baseline.baseline_version
    assert report.macro_average_mae == pytest.approx(4 / 7)
    payload = report.to_dict()
    assert payload["data_classification"] == "PUBLIC_BENCHMARK"
    assert payload["selection"]["selection_inputs"] == "chronological_validation_only"
    assert payload["selection"]["selection_changed_by_final_test"] is False
    assert payload["agent_decision"]["agent"] == "forecast_evaluation"
    persisted_model = SnapshotStore(tmp_path).load_model_run(lifecycle.model_run_id)
    assert persisted_model is not None
    assert persisted_model["selection"] == "RETAINED_BASELINE"
    assert persisted_model["final_test_state"] == "LOCKED_UNEVALUATED"

    with pytest.raises(FinalTestReportError, match="FINAL_TEST_REPORT_ALREADY_EXISTS"):
        PublicBenchmarkFinalTestReporter.for_root(tmp_path).evaluate_and_persist(
            benchmark_run_id=benchmark.run_id,
            baseline_run_id=baseline.run_id,
            model_run_id=lifecycle.model_run_id,
        )


def test_final_test_metrics_use_locked_days_only_after_unchanged_validation_selection(tmp_path) -> None:
    ordinary_root = tmp_path / "ordinary"
    changed_root = tmp_path / "changed"
    ordinary_benchmark, ordinary_baseline, ordinary_model = recorded_lifecycle(ordinary_root, locked_test_value=1.0)
    changed_benchmark, changed_baseline, changed_model = recorded_lifecycle(changed_root, locked_test_value=9.0)

    ordinary_report = PublicBenchmarkFinalTestReporter.for_root(ordinary_root).evaluate_and_persist(
        benchmark_run_id=ordinary_benchmark.run_id,
        baseline_run_id=ordinary_baseline.run_id,
        model_run_id=ordinary_model.model_run_id,
    )
    changed_report = PublicBenchmarkFinalTestReporter.for_root(changed_root).evaluate_and_persist(
        benchmark_run_id=changed_benchmark.run_id,
        baseline_run_id=changed_baseline.run_id,
        model_run_id=changed_model.model_run_id,
    )

    assert ordinary_model.selection == changed_model.selection == "RETAINED_BASELINE"
    assert ordinary_model.evaluations[0].baseline_validation_mae == changed_model.evaluations[0].baseline_validation_mae
    assert ordinary_report.macro_average_mae != changed_report.macro_average_mae


def test_final_test_rejects_tampered_snapshot_without_writing_report(tmp_path) -> None:
    benchmark, baseline, lifecycle = recorded_lifecycle(tmp_path)
    snapshot_path = tmp_path / "snapshots" / benchmark.manifest.snapshot_id / "benchmark_daily_demand.csv"
    snapshot_path.write_text("tampered", encoding="utf-8")

    with pytest.raises(FinalTestReportError, match="FINAL_TEST_SNAPSHOT_TABLE_HASH_MISMATCH"):
        PublicBenchmarkFinalTestReporter.for_root(tmp_path).evaluate_and_persist(
            benchmark_run_id=benchmark.run_id,
            baseline_run_id=baseline.run_id,
            model_run_id=lifecycle.model_run_id,
        )

    assert not (tmp_path / "public-benchmark-final-test-reports").exists()
