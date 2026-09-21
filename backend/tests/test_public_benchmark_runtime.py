"""Contract and end-to-end tests for the local public benchmark runtime."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pandas as pd
from fastapi.testclient import TestClient

from app.api.routes import public_benchmark_runs
from app.config import settings
from app.main import app
from app.runtime.contracts import (
    PublicBenchmarkScope,
    PublicBenchmarkSubmission,
    RuntimeEventName,
    RuntimeStatus,
)
from app.runtime.store import RuntimeStore
from app.runtime.worker import PublicBenchmarkWorker


AS_OF = datetime(2026, 2, 1, tzinfo=timezone.utc)


def submission(key: str = "public-runtime-test-v1") -> PublicBenchmarkSubmission:
    return PublicBenchmarkSubmission(
        idempotency_key=key,
        selection_id="freshretailnet-runtime-fixture",
        scopes=tuple(PublicBenchmarkScope(store_id=101, product_id=index) for index in range(20)),
        as_of=AS_OF,
    )


def source_frame() -> pd.DataFrame:
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
                    "sale_amount": 1.0 if offset < 21 else 5.0,
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


def test_queue_is_idempotent_and_events_survive_new_store_instance(tmp_path) -> None:
    store = RuntimeStore(tmp_path)
    first, created = store.enqueue(submission())
    second, duplicate = RuntimeStore(tmp_path).enqueue(submission())

    assert created is True
    assert duplicate is False
    assert first.run_id == second.run_id
    assert second.status is RuntimeStatus.QUEUED
    assert [event.name for event in RuntimeStore(tmp_path).list_events(first.run_id)] == [
        RuntimeEventName.QUEUED
    ]


def test_expired_worker_lease_is_recovered_with_a_durable_requeue_event(tmp_path) -> None:
    store = RuntimeStore(tmp_path)
    run, _ = store.enqueue(submission())
    first_claim = store.claim_next("worker-one", lease_seconds=60)
    assert first_claim is not None

    with store._connect() as connection:  # Exercise only the expired-lease recovery branch.
        connection.execute(
            "UPDATE runtime_runs SET lease_expires_at = ? WHERE run_id = ?",
            ("2000-01-01T00:00:00+00:00", run.run_id),
        )
    recovered = RuntimeStore(tmp_path).claim_next("worker-two", lease_seconds=60)

    assert recovered is not None
    assert recovered.run_id == run.run_id
    assert recovered.attempt_count == 2
    assert [event.name for event in store.list_events(run.run_id)] == [
        RuntimeEventName.QUEUED,
        RuntimeEventName.CLAIMED,
        RuntimeEventName.REQUEUED,
        RuntimeEventName.CLAIMED,
    ]


def test_missing_configured_source_ends_inconclusive_with_persisted_events(tmp_path) -> None:
    runtime = RuntimeStore(tmp_path / "runtime")
    run, _ = runtime.enqueue(submission())

    completed = PublicBenchmarkWorker(
        runtime,
        audit_root=tmp_path / "audit",
        source_path=None,
        worker_id="test-worker",
    ).run_once()

    assert completed is not None
    assert completed.run_id == run.run_id
    assert completed.status is RuntimeStatus.INCONCLUSIVE
    assert completed.outcome is not None
    assert completed.outcome["reason_code"] == "PUBLIC_BENCHMARK_SOURCE_NOT_CONFIGURED"
    assert [event.name for event in runtime.list_events(run.run_id)] == [
        RuntimeEventName.QUEUED,
        RuntimeEventName.CLAIMED,
        RuntimeEventName.INCONCLUSIVE,
    ]


def test_worker_reuses_existing_lifecycle_and_persists_actual_public_report(tmp_path) -> None:
    source_path = tmp_path / "freshretailnet.parquet"
    source_frame().to_parquet(source_path, index=False)
    runtime = RuntimeStore(tmp_path / "runtime")
    run, _ = runtime.enqueue(submission())

    completed = PublicBenchmarkWorker(
        runtime,
        audit_root=tmp_path / "audit",
        source_path=source_path,
        worker_id="test-worker",
    ).run_once()

    assert completed is not None
    assert completed.status is RuntimeStatus.REPORT_READY
    assert completed.outcome is not None
    assert completed.outcome["final_test_report_id"].startswith("final-test-")
    assert completed.outcome["selection"] == "RETAINED_BASELINE"
    assert completed.outcome["limitations"]
    names = [event.name for event in runtime.list_events(run.run_id)]
    assert names == [
        RuntimeEventName.QUEUED,
        RuntimeEventName.CLAIMED,
        RuntimeEventName.VALIDATING,
        RuntimeEventName.SNAPSHOT_STORED,
        RuntimeEventName.BASELINE_EVALUATED,
        RuntimeEventName.MODEL_SELECTED,
        RuntimeEventName.FINAL_TEST_REPORTED,
        RuntimeEventName.REPORT_READY,
    ]


def test_api_queues_and_reads_persisted_public_events_without_browser_source_path(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        public_benchmark_runs,
        "settings",
        replace(settings, runtime_root=tmp_path / "runtime"),
    )
    payload = {
        "idempotency_key": "api-public-runtime-v1",
        "selection_id": "api-selection",
        "scopes": [{"store_id": 101, "product_id": index} for index in range(20)],
        "as_of": AS_OF.isoformat(),
    }

    first = TestClient(app).post("/v1/public-benchmark-runs", json=payload)
    duplicate = TestClient(app).post("/v1/public-benchmark-runs", json=payload)

    assert first.status_code == 201
    assert duplicate.status_code == 200
    created = first.json()
    assert created["source_mode"] == "PUBLIC_BENCHMARK"
    assert "source_path" not in created
    events = TestClient(app).get(f"/v1/public-benchmark-runs/{created['run_id']}/events")
    assert events.status_code == 200
    assert [item["name"] for item in events.json()["events"]] == ["QUEUED"]


def test_api_copilot_is_hard_disabled_until_all_server_side_gates_are_configured(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        public_benchmark_runs,
        "settings",
        replace(settings, runtime_root=tmp_path / "runtime", audit_root=tmp_path / "audit"),
    )
    payload = {
        "idempotency_key": "copilot-disabled-v1",
        "selection_id": "copilot-disabled-selection",
        "scopes": [{"store_id": 101, "product_id": index} for index in range(20)],
        "as_of": AS_OF.isoformat(),
    }
    created = TestClient(app).post("/v1/public-benchmark-runs", json=payload).json()

    response = TestClient(app).post(
        f"/v1/public-benchmark-runs/{created['run_id']}/planner-briefs"
    )

    assert response.status_code == 503
    assert "COPILOT_NOT_ENABLED" in response.json()["detail"]


def test_api_rejects_an_untrusted_operator_before_a_configured_copilot_can_spend(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        public_benchmark_runs,
        "settings",
        replace(
            settings,
            runtime_root=tmp_path / "runtime",
            audit_root=tmp_path / "audit",
            planner_copilot_operator_token="operator-secret",
        ),
    )
    payload = {
        "idempotency_key": "copilot-operator-v1",
        "selection_id": "copilot-operator-selection",
        "scopes": [{"store_id": 101, "product_id": index} for index in range(20)],
        "as_of": AS_OF.isoformat(),
    }
    created = TestClient(app).post("/v1/public-benchmark-runs", json=payload).json()

    response = TestClient(app).post(
        f"/v1/public-benchmark-runs/{created['run_id']}/planner-briefs"
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "COPILOT_OPERATOR_TOKEN_INVALID"
