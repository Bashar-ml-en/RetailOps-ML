"""Synthetic-fixture tests for the fixed, chronology-safe candidate lifecycle."""

from datetime import datetime, timedelta, timezone

from app.schemas.connector import DataContractResult, SnapshotManifest
from app.schemas.forecast import BaselineRunRequest, ModelLifecycleRequest
from app.services.forecasting import BaselineRunner
from app.services.model_lifecycle import (
    CANDIDATE_VERSION,
    MODEL_REGISTRY_SCHEMA_VERSION,
    ModelLifecycleRunner,
)
from app.services.storage import SnapshotStore
from app.services.validation import CsvBundle


AS_OF = datetime(2026, 2, 1, tzinfo=timezone.utc)
SNAPSHOT_ID = "snapshot-lifecycle-fixture-001"


def manifest() -> SnapshotManifest:
    return SnapshotManifest(
        snapshot_id=SNAPSHOT_ID,
        tenant_id="fixture-tenant",
        source_type="CSV",
        source_name="synthetic-test-fixture",
        authorization_reference="test-only",
        mapping_version="fixture-v1",
        retrieved_at=AS_OF,
        source_hash="c" * 64,
        schema_hash="d" * 64,
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


def baseline_request() -> BaselineRunRequest:
    return BaselineRunRequest(
        tenant_id="fixture-tenant",
        snapshot_id=SNAPSHOT_ID,
        operating_timezone="UTC",
        minimum_training_days=14,
        validation_days=7,
        locked_test_days=7,
    )


def lifecycle_request(baseline_run_id: str, **overrides: str) -> ModelLifecycleRequest:
    values = {
        "tenant_id": "fixture-tenant",
        "snapshot_id": SNAPSHOT_ID,
        "baseline_run_id": baseline_run_id,
    }
    values.update(overrides)
    return ModelLifecycleRequest(**values)


def bundle(quantities: list[int]) -> CsvBundle:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    order_rows = ["order_id,sku,location_id,occurred_at,quantity,status"]
    for index, quantity in enumerate(quantities):
        occurred_at = start + timedelta(days=index)
        order_rows.append(
            f"order-{index},sku-1,store-1,{occurred_at.isoformat()},{quantity},completed"
        )
    return CsvBundle.from_text(
        {
            "products": "product_id,sku,name,quantity_unit\np-1,sku-1,Fixture item,each\n",
            "locations": "location_id,name,type\nstore-1,Fixture store,store\n",
            "order_lines": "\n".join(order_rows) + "\n",
            "inventory_snapshots": "snapshot_at,sku,location_id,on_hand\n2026-02-01T00:00:00+00:00,sku-1,store-1,10\n",
        }
    )


def baseline_for(source: CsvBundle):
    return BaselineRunner().run(
        baseline_request(), manifest=manifest(), data_contract=accepted_contract(), bundle=source
    )


def test_fixed_candidate_promotes_only_after_strict_validation_improvement_and_registers(tmp_path) -> None:
    # Alternating demand makes the fixed trailing mean strictly better than the last observation.
    source = bundle([1 if index % 2 == 0 else 0 for index in range(28)])
    baseline = baseline_for(source)

    run = ModelLifecycleRunner().run(
        lifecycle_request(baseline.run_id),
        manifest=manifest(),
        data_contract=accepted_contract(),
        baseline_run=baseline,
        bundle=source,
    )

    assert run.status == "PASS"
    assert run.candidate_configuration.model_version == CANDIDATE_VERSION
    assert run.selection == "PROMOTED_CANDIDATE"
    assert run.selected_model_version == CANDIDATE_VERSION
    assert run.rollback_baseline_version == baseline.baseline_version
    assert run.rollback_baseline_run_id == baseline.run_id
    assert run.evaluations[0].candidate_validation_mae < run.evaluations[0].baseline_validation_mae
    assert run.to_dict()["final_test_state"] == "LOCKED_UNEVALUATED"
    assert run.to_dict()["evaluations"][0]["final_test_state"] == "LOCKED_UNEVALUATED"
    assert run.agent_decision is not None
    assert run.agent_decision["agent"] == "forecast_evaluation"

    store = SnapshotStore(tmp_path)
    store.persist_model_run(run)
    registered = store.load_model_run(run.model_run_id)
    assert registered is not None
    assert registered["registry_schema_version"] == MODEL_REGISTRY_SCHEMA_VERSION
    assert registered["candidate_configuration"]["model_version"] == CANDIDATE_VERSION
    assert registered["rollback_baseline"]["baseline_run_id"] == baseline.run_id


def test_tied_candidate_retains_the_registered_baseline() -> None:
    source = bundle([1] * 28)
    baseline = baseline_for(source)

    run = ModelLifecycleRunner().run(
        lifecycle_request(baseline.run_id),
        manifest=manifest(),
        data_contract=accepted_contract(),
        baseline_run=baseline,
        bundle=source,
    )

    assert run.status == "PASS"
    assert run.selection == "RETAINED_BASELINE"
    assert run.selected_model_version == baseline.baseline_version
    assert run.evaluations[0].candidate_validation_mae == run.evaluations[0].baseline_validation_mae
    assert run.selection_rationale.startswith("candidate_tied_or_regressed")


def test_scope_mismatch_is_rejected_before_candidate_evaluation() -> None:
    source = bundle([1] * 28)
    baseline = baseline_for(source)

    run = ModelLifecycleRunner().run(
        lifecycle_request(baseline.run_id, snapshot_id="another-snapshot"),
        manifest=manifest(),
        data_contract=accepted_contract(),
        baseline_run=baseline,
        bundle=source,
    )

    assert run.status == "REJECT"
    assert run.selection == "NOT_EVALUATED"
    assert run.evaluations == ()
    assert run.limitations == ("SNAPSHOT_SCOPE_MISMATCH",)


def test_unaccepted_snapshot_cannot_enter_candidate_evaluation() -> None:
    source = bundle([1] * 28)
    baseline = baseline_for(source)
    unaccepted_contract = DataContractResult(
        status="INCONCLUSIVE",
        approved_uses=("demand_forecast",),
        blocked_uses=("inventory_risk",),
        limitations=("STALE_SNAPSHOT",),
        next_action="refresh_snapshot",
    )

    run = ModelLifecycleRunner().run(
        lifecycle_request(baseline.run_id),
        manifest=manifest(),
        data_contract=unaccepted_contract,
        baseline_run=baseline,
        bundle=source,
    )

    assert run.status == "INCONCLUSIVE"
    assert run.selection == "NOT_EVALUATED"
    assert run.evaluations == ()
    assert run.limitations == ("DATA_CONTRACT_NOT_ACCEPTED", "STALE_SNAPSHOT")


def test_candidate_metrics_do_not_use_locked_final_test_values() -> None:
    validation_history = [1 if index % 2 == 0 else 0 for index in range(21)]
    ordinary_source = bundle(validation_history + [0] * 7)
    changed_test_source = bundle(validation_history + [1000] * 7)
    ordinary_baseline = baseline_for(ordinary_source)
    changed_test_baseline = baseline_for(changed_test_source)

    ordinary_run = ModelLifecycleRunner().run(
        lifecycle_request(ordinary_baseline.run_id),
        manifest=manifest(),
        data_contract=accepted_contract(),
        baseline_run=ordinary_baseline,
        bundle=ordinary_source,
    )
    changed_test_run = ModelLifecycleRunner().run(
        lifecycle_request(changed_test_baseline.run_id),
        manifest=manifest(),
        data_contract=accepted_contract(),
        baseline_run=changed_test_baseline,
        bundle=changed_test_source,
    )

    ordinary_evaluation = ordinary_run.evaluations[0]
    changed_test_evaluation = changed_test_run.evaluations[0]
    assert ordinary_evaluation.baseline_validation_mae == changed_test_evaluation.baseline_validation_mae
    assert ordinary_evaluation.candidate_validation_mae == changed_test_evaluation.candidate_validation_mae
    assert ordinary_evaluation.candidate_validation_rmse == changed_test_evaluation.candidate_validation_rmse
    assert ordinary_run.selection == changed_test_run.selection
    assert ordinary_evaluation.locked_test_start.isoformat() == "2026-01-22"
    assert ordinary_run.to_dict()["final_test_state"] == "LOCKED_UNEVALUATED"
