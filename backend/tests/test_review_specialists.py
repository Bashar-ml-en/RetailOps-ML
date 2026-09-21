"""Fixture and safety-boundary tests for deterministic Stage 5 specialists."""

from datetime import datetime, timedelta, timezone

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
    ReviewScope,
)


AS_OF = datetime(2026, 9, 16, 10, 0, tzinfo=timezone.utc)


def scope() -> ReviewScope:
    return ReviewScope(
        tenant_id="fixture-tenant",
        snapshot_id="fixture-snapshot-1",
        sku="sku-1",
        location_id="store-1",
        quantity_unit="each",
    )


def risk_request(**overrides: object) -> InventoryRiskRequest:
    values: dict[str, object] = {
        "run_id": "risk-run-1",
        "data_classification": "FIXTURE",
        "scope": scope(),
        "forecast": ForecastEvidence(
            model_run_id="model-run-1",
            model_version="fixture-baseline-v1",
            horizon_days=7,
            forecast_quantity=70,
        ),
        "as_of": AS_OF,
        "data_contract_status": "PASS",
        "forecast_evaluation_status": "PASS",
        "inventory_observed_at": AS_OF - timedelta(hours=1),
        "on_hand_quantity": 5,
        "inbound_supply": (
            InboundSupplyEvidence(
                supply_id="supply-1",
                expected_at=AS_OF + timedelta(days=2),
                quantity=5,
                confirmed=True,
            ),
        ),
        "inbound_supply_complete": True,
        "lead_time_days": 5,
    }
    values.update(overrides)
    return InventoryRiskRequest(**values)


def qualified_fixture_chain():
    risk = InventoryRiskAgent().decide(risk_request())
    ranking = ImpactRankingAgent().decide(
        ImpactRankingRequest(
            run_id="ranking-run-1",
            data_classification="FIXTURE",
            risk_cases=(risk,),
        )
    )
    critic = PolicyCriticAgent().decide(
        PolicyCriticRequest(
            run_id="critic-run-1",
            data_classification="FIXTURE",
            data_contract_status="PASS",
            forecast_evaluation_status="PASS",
            inventory_risk=risk,
            impact_ranking=ranking,
        )
    )
    return risk, ranking, critic


def test_fixture_chain_is_deterministic_review_only_and_never_external() -> None:
    risk, ranking, critic = qualified_fixture_chain()
    draft = ActionDraftingAgent().decide(
        ActionDraftRequest(
            run_id="draft-run-1",
            data_classification="FIXTURE",
            planner_owner_role="pilot_planner",
            inventory_risk=risk,
            impact_ranking=ranking,
            policy_critic=critic,
        )
    )

    assert risk.status == "PASS_WITH_LIMITATIONS"
    assert risk.risk_case_qualified is True
    assert risk.forecast_daily_rate == 10
    assert risk.demand_during_lead_time == 50
    assert risk.confirmed_supply_during_lead_time == 5
    assert risk.shortfall_quantity == 40
    assert ranking.status == "PASS_WITH_LIMITATIONS"
    assert ranking.ranked_cases[0].rank == 1
    assert critic.status == "PASS_WITH_LIMITATIONS"
    assert critic.approved_for_action_draft is True
    assert draft.status == "PASS_WITH_LIMITATIONS"
    assert draft.draft is not None
    assert draft.draft.external_execution_permitted is False
    assert draft.agent_decision.next_action == "enqueue_fixture_review_case"


def test_missing_lead_time_or_public_benchmark_evidence_fails_closed_without_a_case() -> None:
    missing_lead_time = InventoryRiskAgent().decide(risk_request(lead_time_days=None))
    public_benchmark = InventoryRiskAgent().decide(
        risk_request(data_classification="PUBLIC_BENCHMARK")
    )

    assert missing_lead_time.status == "INCONCLUSIVE"
    assert missing_lead_time.risk_case_qualified is None
    assert missing_lead_time.agent_decision.limitations == ("MISSING_LEAD_TIME",)
    assert public_benchmark.status == "INCONCLUSIVE"
    assert public_benchmark.risk_case_qualified is None
    assert public_benchmark.agent_decision.limitations == (
        "PUBLIC_BENCHMARK_INVENTORY_RISK_BLOCKED",
    )


def test_critic_vetoes_external_operation_and_action_drafting_returns_no_draft() -> None:
    risk, ranking, _ = qualified_fixture_chain()
    critic = PolicyCriticAgent().decide(
        PolicyCriticRequest(
            run_id="critic-veto-run-1",
            data_classification="FIXTURE",
            data_contract_status="PASS",
            forecast_evaluation_status="PASS",
            inventory_risk=risk,
            impact_ranking=ranking,
            requested_action="EXTERNAL_OPERATION",
        )
    )
    draft = ActionDraftingAgent().decide(
        ActionDraftRequest(
            run_id="draft-veto-run-1",
            data_classification="FIXTURE",
            planner_owner_role="pilot_planner",
            inventory_risk=risk,
            impact_ranking=ranking,
            policy_critic=critic,
        )
    )

    assert critic.status == "REJECT"
    assert critic.approved_for_action_draft is False
    assert critic.agent_decision.limitations == ("EXTERNAL_OPERATION_PROHIBITED",)
    assert draft.status == "INCONCLUSIVE"
    assert draft.draft is None
    assert draft.agent_decision.limitations == ("POLICY_CRITIC_NOT_APPROVED",)
