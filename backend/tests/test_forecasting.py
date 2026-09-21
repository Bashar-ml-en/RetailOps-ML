"""Synthetic-fixture tests for the chronology-safe demand baseline."""

from datetime import datetime, timedelta, timezone

from app.schemas.connector import DataContractResult, SnapshotManifest
from app.schemas.forecast import BaselineRunRequest
from app.services.forecasting import BASELINE_VERSION, BaselineRunner
from app.services.storage import SnapshotStore
from app.services.validation import CsvBundle


AS_OF = datetime(2026, 2, 1, tzinfo=timezone.utc)
SNAPSHOT_ID = "snapshot-fixture-001"


def manifest() -> SnapshotManifest:
    return SnapshotManifest(
        snapshot_id=SNAPSHOT_ID,
        tenant_id="fixture-tenant",
        source_type="CSV",
        source_name="synthetic-test-fixture",
        authorization_reference="test-only",
        mapping_version="fixture-v1",
        retrieved_at=AS_OF,
        source_hash="a" * 64,
        schema_hash="b" * 64,
        table_hashes={},
        row_counts={},
        excluded_counts={},
    )


def accepted_contract() -> DataContractResult:
    return DataContractResult(
        status="PASS",
        approved_uses=("demand_forecast",),
        blocked_uses=("inventory_risk", "replenishment_draft"),
        limitations=(),
        next_action="build_demand_series",
    )


def request(**overrides: object) -> BaselineRunRequest:
    values: dict[str, object] = {
        "tenant_id": "fixture-tenant",
        "snapshot_id": SNAPSHOT_ID,
        "operating_timezone": "UTC",
        "minimum_training_days": 14,
        "validation_days": 7,
        "locked_test_days": 7,
    }
    values.update(overrides)
    return BaselineRunRequest(**values)


def bundle(days: int = 28, *, future_row: bool = False) -> CsvBundle:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    order_rows = ["order_id,sku,location_id,occurred_at,quantity,status"]
    for index in range(days):
        occurred_at = start + timedelta(days=index)
        order_rows.append(f"order-{index},sku-1,store-1,{occurred_at.isoformat()},1,completed")
    if future_row:
        order_rows.append("future,sku-1,store-1,2026-02-02T00:00:00+00:00,1,completed")
    return CsvBundle.from_text(
        {
            "products": "product_id,sku,name,quantity_unit\np-1,sku-1,Fixture item,each\n",
            "locations": "location_id,name,type\nstore-1,Fixture store,store\n",
            "order_lines": "\n".join(order_rows) + "\n",
            "inventory_snapshots": "snapshot_at,sku,location_id,on_hand\n2026-02-01T00:00:00+00:00,sku-1,store-1,10\n",
        }
    )


def test_baseline_uses_validation_only_and_leaves_the_final_test_locked(tmp_path) -> None:
    run = BaselineRunner().run(
        request(), manifest=manifest(), data_contract=accepted_contract(), bundle=bundle()
    )

    assert run.status == "PASS"
    assert run.baseline_version == BASELINE_VERSION
    assert len(run.evaluations) == 1
    evaluation = run.evaluations[0]
    assert evaluation.training_days == 14
    assert evaluation.validation_days == 7
    assert evaluation.locked_test_days == 7
    assert evaluation.validation_start.isoformat() == "2026-01-15"
    assert evaluation.locked_test_start.isoformat() == "2026-01-22"
    assert evaluation.validation_mae == 0.0
    assert evaluation.validation_rmse == 0.0
    assert run.to_dict()["evaluations"][0]["final_test_state"] == "LOCKED_UNEVALUATED"
    assert run.agent_decision is not None
    assert run.agent_decision["agent"] == "forecast_evaluation"

    store = SnapshotStore(tmp_path)
    store.persist_baseline_run(run)
    assert store.load_baseline_run(run.run_id)["status"] == "PASS"


def test_future_order_observation_is_rejected_before_baseline_evaluation() -> None:
    run = BaselineRunner().run(
        request(),
        manifest=manifest(),
        data_contract=accepted_contract(),
        bundle=bundle(future_row=True),
    )

    assert run.status == "REJECT"
    assert run.evaluations == ()
    assert run.limitations == ("FUTURE_ORDER_OBSERVATION",)


def test_insufficient_history_is_inconclusive_and_cannot_register_a_baseline() -> None:
    run = BaselineRunner().run(
        request(), manifest=manifest(), data_contract=accepted_contract(), bundle=bundle(days=20)
    )

    assert run.status == "INCONCLUSIVE"
    assert run.evaluations == ()
    assert run.next_action == "request_eligible_history"
    assert run.limitations[0].startswith("INSUFFICIENT_HISTORY:")
