"""Tests for the persisted, fixture-only specialist workflow event stream."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone

from app.schemas.review import (
    ForecastEvidence,
    InboundSupplyEvidence,
    InventoryRiskRequest,
    ReviewScope,
)
from app.schemas.workflow import FixtureReviewWorkflowRequest
from app.services.review_queue import FixtureReviewQueue, ReviewQueueError
from app.services.review_workflow import FixtureReviewWorkflowOrchestrator
from app.services.storage import SnapshotStore


AS_OF = datetime(2026, 9, 16, 10, 0, tzinfo=timezone.utc)


def workflow_request() -> FixtureReviewWorkflowRequest:
    """Create complete, declared fixture evidence that qualifies one review case."""

    inventory_request = InventoryRiskRequest(
        run_id="workflow-input-risk-1",
        data_classification="FIXTURE",
        scope=ReviewScope(
            tenant_id="fixture-tenant",
            snapshot_id="fixture-snapshot-workflow",
            sku="sku-1",
            location_id="store-1",
            quantity_unit="each",
        ),
        forecast=ForecastEvidence(
            model_run_id="fixture-model-workflow-1",
            model_version="fixture-baseline-v1",
            horizon_days=7,
            forecast_quantity=70,
        ),
        as_of=AS_OF,
        data_contract_status="PASS",
        forecast_evaluation_status="PASS",
        inventory_observed_at=AS_OF - timedelta(hours=1),
        on_hand_quantity=5,
        inbound_supply=(
            InboundSupplyEvidence(
                supply_id="fixture-supply-workflow-1",
                expected_at=AS_OF + timedelta(days=2),
                quantity=5,
                confirmed=True,
            ),
        ),
        inbound_supply_complete=True,
        lead_time_days=5,
    )
    return FixtureReviewWorkflowRequest(
        data_classification="FIXTURE",
        data_contract_status="PASS",
        forecast_evaluation_status="PASS",
        inventory_risk_request=inventory_request,
        planner_owner_role="pilot_planner",
    )


def test_workflow_persists_actual_critic_approved_fixture_transitions(tmp_path) -> None:
    store = SnapshotStore(tmp_path)
    workflow = FixtureReviewWorkflowOrchestrator(store, clock=lambda: AS_OF)

    run = workflow.run(workflow_request())

    assert run.status == "REVIEW_READY"
    assert run.review_case_id is not None
    assert [event.name for event in run.events] == [
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
    ]
    assert [event.sequence for event in run.events] == list(range(1, 11))
    assert all(event.evidence_refs for event in run.events[1:])
    assert all("FIXTURE_ONLY_NOT_OPERATIONAL" in event.limitations for event in run.events[5:9])

    persisted = store.load_fixture_review_workflow_run(run.workflow_run_id)
    assert persisted is not None
    assert persisted["status"] == "REVIEW_READY"
    assert persisted["external_execution_permitted"] is False
    assert persisted["review_case_id"] == run.review_case_id
    assert FixtureReviewQueue(store, clock=lambda: AS_OF).get_case(run.review_case_id) is not None


def test_workflow_stops_inconclusive_without_a_review_case_when_lead_time_is_missing(tmp_path) -> None:
    store = SnapshotStore(tmp_path)
    workflow = FixtureReviewWorkflowOrchestrator(store, clock=lambda: AS_OF)
    request = workflow_request()
    missing_lead_time = replace(request.inventory_risk_request, lead_time_days=None)

    run = workflow.run(replace(request, inventory_risk_request=missing_lead_time))

    assert run.status == "INCONCLUSIVE"
    assert run.review_case_id is None
    assert [event.name for event in run.events] == [
        "QUEUED",
        "VALIDATING",
        "DATA_CONTRACT_REVIEWED",
        "FORECAST_EVALUATION_REVIEWED",
        "FEATURES_READY",
        "INVENTORY_RISK_REVIEWED",
        "INCONCLUSIVE",
    ]
    assert run.events[-1].limitations == ("MISSING_LEAD_TIME",)
    assert not store.review_cases_root.exists()


def test_workflow_rejects_non_fixture_input_before_specialist_execution(tmp_path) -> None:
    store = SnapshotStore(tmp_path)
    workflow = FixtureReviewWorkflowOrchestrator(store, clock=lambda: AS_OF)
    request = workflow_request()

    run = workflow.run(replace(request, data_classification="PUBLIC_BENCHMARK"))  # type: ignore[arg-type]

    assert run.status == "REJECTED"
    assert run.review_case_id is None
    assert [event.name for event in run.events] == ["QUEUED", "VALIDATING", "REJECTED"]
    assert run.events[-1].limitations == ("WORKFLOW_FIXTURE_ONLY",)
    assert not store.review_cases_root.exists()


def test_workflow_persists_failed_terminal_event_when_local_queue_refuses_case(tmp_path) -> None:
    class RefusingFixtureQueue:
        def enqueue(self, **_: object) -> None:
            raise ReviewQueueError("FIXTURE_QUEUE_REFUSED")

    store = SnapshotStore(tmp_path)
    workflow = FixtureReviewWorkflowOrchestrator(
        store,
        queue=RefusingFixtureQueue(),  # type: ignore[arg-type]
        clock=lambda: AS_OF,
    )

    run = workflow.run(workflow_request())

    assert run.status == "FAILED"
    assert run.review_case_id is None
    assert run.events[-2].name == "ACTION_DRAFTED"
    assert run.events[-1].name == "FAILED"
    assert run.events[-1].limitations == ("FIXTURE_QUEUE_REFUSED",)
    assert store.load_fixture_review_workflow_run(run.workflow_run_id) is not None
    assert not store.review_cases_root.exists()
