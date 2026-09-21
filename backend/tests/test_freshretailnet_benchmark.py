"""Contract tests for the explicitly limited FreshRetailNet benchmark adapter."""

from datetime import datetime, timedelta, timezone
import hashlib

import pandas as pd
import pytest

from app.schemas.benchmark import (
    FRESHRETAILNET_BENCHMARK_TENANT_ID,
    FreshRetailNetBenchmarkRequest,
    FreshRetailNetScope,
)
from app.schemas.forecast import BaselineRunRequest, ModelLifecycleRequest
from app.services.forecasting import BaselineRunner
from app.services.freshretailnet import (
    BENCHMARK_DAILY_DEMAND_TABLE,
    BENCHMARK_LIMITATIONS,
    FreshRetailNetBenchmarkRunner,
    FreshRetailNetMappingError,
)
from app.services.model_lifecycle import ModelLifecycleRunner
from app.services.series import build_daily_demand_series
from app.services.storage import SnapshotStore


AS_OF = datetime(2026, 2, 1, tzinfo=timezone.utc)


def request(**overrides: object) -> FreshRetailNetBenchmarkRequest:
    values: dict[str, object] = {
        "selection_id": "frn-public-benchmark-subset-a",
        "scopes": tuple(FreshRetailNetScope(store_id=101, product_id=product_id) for product_id in range(20)),
        "as_of": AS_OF,
    }
    values.update(overrides)
    return FreshRetailNetBenchmarkRequest(**values)


def source_frame(*, days: int = 28, gap: bool = False) -> pd.DataFrame:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    rows: list[dict[str, object]] = []
    for product_id in range(20):
        for offset in range(days):
            if gap and product_id == 0 and offset == 10:
                continue
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
                    "sale_amount": 1.0 if offset % 2 == 0 else 0.0,
                    "hours_sale": "[]",
                    "stock_hour6_22_cnt": 1 if offset == 4 else 0,
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


def test_public_benchmark_is_versioned_limited_and_can_enter_local_forecast_evaluation(tmp_path) -> None:
    materialization = FreshRetailNetBenchmarkRunner.for_root(tmp_path).run(request(), source_frame())
    run = materialization.run

    assert run.manifest.source_type == "PUBLIC_BENCHMARK"
    assert run.manifest.data_classification == "PUBLIC_BENCHMARK"
    assert run.result.status == "PASS_WITH_LIMITATIONS"
    assert run.result.approved_uses == ("demand_forecast",)
    assert run.result.blocked_uses == (
        "inventory_risk",
        "replenishment_draft",
        "production_scoring",
    )
    assert set(BENCHMARK_LIMITATIONS).issubset(run.result.limitations)
    assert "inventory_snapshots" not in materialization.bundle.tables
    assert BENCHMARK_DAILY_DEMAND_TABLE in materialization.bundle.tables
    assert SnapshotStore(tmp_path).load_public_benchmark_run(run.run_id)["source_type"] == "PUBLIC_BENCHMARK"

    daily = build_daily_demand_series(
        materialization.bundle, operating_timezone="UTC", as_of=AS_OF
    )
    assert len(daily.series) == 20
    assert daily.series[0].quantities[:4] == (1.0, 0.0, 1.0, 0.0)

    baseline = BaselineRunner().run(
        BaselineRunRequest(
            tenant_id=FRESHRETAILNET_BENCHMARK_TENANT_ID,
            snapshot_id=run.manifest.snapshot_id,
            operating_timezone="UTC",
        ),
        manifest=run.manifest,
        data_contract=run.result,
        bundle=materialization.bundle,
    )
    assert baseline.status == "PASS_WITH_LIMITATIONS"
    assert set(BENCHMARK_LIMITATIONS).issubset(baseline.limitations)
    assert len(baseline.evaluations) == 20

    lifecycle = ModelLifecycleRunner().run(
        ModelLifecycleRequest(
            tenant_id=FRESHRETAILNET_BENCHMARK_TENANT_ID,
            snapshot_id=run.manifest.snapshot_id,
            baseline_run_id=baseline.run_id,
        ),
        manifest=run.manifest,
        data_contract=run.result,
        baseline_run=baseline,
        bundle=materialization.bundle,
    )
    assert lifecycle.status == "PASS_WITH_LIMITATIONS"
    assert lifecycle.selection == "PROMOTED_CANDIDATE"
    assert set(BENCHMARK_LIMITATIONS).issubset(lifecycle.limitations)
    assert lifecycle.to_dict()["final_test_state"] == "LOCKED_UNEVALUATED"


def test_missing_selected_scope_is_rejected_without_creating_a_snapshot(tmp_path) -> None:
    frame = source_frame()
    frame = frame[frame["product_id"] != 19]

    with pytest.raises(FreshRetailNetMappingError, match="UNMAPPED_FRESHRETAILNET_SCOPE"):
        FreshRetailNetBenchmarkRunner.for_root(tmp_path).run(request(), frame)

    assert not (tmp_path / "snapshots").exists()


def test_parquet_entrypoint_checks_source_schema_and_records_raw_file_hash(tmp_path) -> None:
    source_path = tmp_path / "train.parquet"
    source_frame().to_parquet(source_path, index=False)

    materialization = FreshRetailNetBenchmarkRunner.for_root(tmp_path / "audit").run_from_parquet(
        request(), source_path
    )

    expected_hash = hashlib.sha256(source_path.read_bytes()).hexdigest()
    assert materialization.run.request.source_file_name == "train.parquet"
    assert materialization.run.request.source_file_sha256 == expected_hash
    assert materialization.run.manifest.source_reference.endswith(
        "/data/train.parquet"
    )


def test_gapped_daily_observation_is_rejected_without_filling_missing_days(tmp_path) -> None:
    with pytest.raises(FreshRetailNetMappingError, match="GAPPED_FRESHRETAILNET_DAILY_OBSERVATION"):
        FreshRetailNetBenchmarkRunner.for_root(tmp_path).run(request(), source_frame(gap=True))

    assert not (tmp_path / "snapshots").exists()
