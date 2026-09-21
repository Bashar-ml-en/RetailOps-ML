"""Audit and safety tests for the fixture-only persisted reviewer queue."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from app.agents.critic import PolicyCriticAgent
from app.agents.inventory_risk import InventoryRiskAgent
from app.agents.market_scope import ImpactRankingAgent
from app.agents.reporter import ActionDraftingAgent
from app.schemas.review import (
    ActionDraftRequest,
    ForecastEvidence,
    ImpactRankingRequest,
    InboundSupplyEvidence,
    InventoryRiskRequest,
    PolicyCriticRequest,
    ReviewDecisionRequest,
    ReviewScope,
)
from app.services.review_queue import FixtureReviewQueue, ReviewQueueError
from app.services.storage import SnapshotStore


AS_OF = datetime(2026, 9, 16, 10, 0, tzinfo=timezone.utc)


def approved_fixture_chain():
    scope = ReviewScope(
        tenant_id="fixture-tenant",
        snapshot_id="fixture-snapshot-queue",
        sku="sku-1",
        location_id="store-1",
        quantity_unit="each",
    )
    risk = InventoryRiskAgent().decide(
        InventoryRiskRequest(
            run_id="risk-queue-1",
            data_classification="FIXTURE",
            scope=scope,
            forecast=ForecastEvidence(
                model_run_id="model-queue-1",
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
                    supply_id="supply-queue-1",
                    expected_at=AS_OF + timedelta(days=2),
                    quantity=5,
                    confirmed=True,
                ),
            ),
            inbound_supply_complete=True,
            lead_time_days=5,
        )
    )
    ranking = ImpactRankingAgent().decide(
        ImpactRankingRequest(
            run_id="ranking-queue-1", data_classification="FIXTURE", risk_cases=(risk,)
        )
    )
    critic = PolicyCriticAgent().decide(
        PolicyCriticRequest(
            run_id="critic-queue-1",
            data_classification="FIXTURE",
            data_contract_status="PASS",
            forecast_evaluation_status="PASS",
            inventory_risk=risk,
            impact_ranking=ranking,
        )
    )
    draft = ActionDraftingAgent().decide(
        ActionDraftRequest(
            run_id="draft-queue-1",
            data_classification="FIXTURE",
            planner_owner_role="pilot_planner",
            inventory_risk=risk,
            impact_ranking=ranking,
            policy_critic=critic,
        )
    )
    return risk, ranking, critic, draft


def test_fixture_case_records_defer_then_approval_as_immutable_nonexecuting_events(tmp_path) -> None:
    risk, ranking, critic, draft = approved_fixture_chain()
    times = iter(
        (
            AS_OF,
            AS_OF + timedelta(minutes=1),
            AS_OF + timedelta(minutes=2),
        )
    )
    queue = FixtureReviewQueue(SnapshotStore(tmp_path), clock=lambda: next(times))
    case = queue.enqueue(
        action_draft=draft,
        policy_critic=critic,
        inventory_risk=risk,
        impact_ranking=ranking,
    )

    initial = queue.get_case(case.case_id)
    assert initial is not None
    assert initial.state == "READY_FOR_REVIEW"
    assert initial.case.data_classification == "FIXTURE"
    assert initial.case.draft.external_execution_permitted is False
    assert (tmp_path / "review-cases" / f"{case.case_id}.json").is_file()

    deferred = queue.record_decision(
        ReviewDecisionRequest(
            case_id=case.case_id,
            planner_owner_role="pilot_planner",
            outcome="DEFER",
            reason="Awaiting fixture review meeting.",
        )
    )
    approved = queue.record_decision(
        ReviewDecisionRequest(
            case_id=case.case_id,
            planner_owner_role="pilot_planner",
            outcome="APPROVE",
            reason="Approved fixture review outcome.",
        )
    )

    summary = queue.get_case(case.case_id)
    assert summary is not None
    assert summary.state == "APPROVED"
    assert [event.outcome for event in summary.decisions] == ["DEFER", "APPROVE"]
    assert deferred.external_execution_permitted is False
    assert approved.external_execution_permitted is False
    assert (tmp_path / "review-decisions" / f"{deferred.decision_id}.json").is_file()
    assert (tmp_path / "review-decisions" / f"{approved.decision_id}.json").is_file()

    with pytest.raises(ReviewQueueError, match="REVIEW_CASE_ALREADY_TERMINAL"):
        queue.record_decision(
            ReviewDecisionRequest(
                case_id=case.case_id,
                planner_owner_role="pilot_planner",
                outcome="DECLINE",
                reason="A terminal decision cannot be replaced.",
            )
        )


def test_queue_rejects_non_fixture_cases_and_wrong_planner_role(tmp_path) -> None:
    risk, ranking, critic, draft = approved_fixture_chain()
    queue = FixtureReviewQueue(SnapshotStore(tmp_path), clock=lambda: AS_OF)

    with pytest.raises(ReviewQueueError, match="REVIEW_QUEUE_FIXTURE_ONLY"):
        queue.enqueue(
            action_draft=replace(draft, data_classification="AUTHORISED_RETAILER"),
            policy_critic=critic,
            inventory_risk=risk,
            impact_ranking=ranking,
        )
    with pytest.raises(ReviewQueueError, match="REVIEW_QUEUE_FIXTURE_ONLY"):
        queue.enqueue(
            action_draft=replace(draft, data_classification="PUBLIC_BENCHMARK"),
            policy_critic=critic,
            inventory_risk=risk,
            impact_ranking=ranking,
        )

    case = queue.enqueue(
        action_draft=draft,
        policy_critic=critic,
        inventory_risk=risk,
        impact_ranking=ranking,
    )
    with pytest.raises(ReviewQueueError, match="PLANNER_ROLE_MISMATCH"):
        queue.record_decision(
            ReviewDecisionRequest(
                case_id=case.case_id,
                planner_owner_role="another_role",
                outcome="DECLINE",
                reason="Role cannot make this fixture decision.",
            )
        )
