"""Real local transitions for the fixture-only specialist and reviewer-queue path."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from collections.abc import Callable
from uuid import uuid4

from app.agents.critic import PolicyCriticAgent
from app.agents.inventory_risk import InventoryRiskAgent
from app.agents.market_scope import ImpactRankingAgent
from app.agents.reporter import ActionDraftingAgent
from app.schemas.review import ActionDraftRequest, ImpactRankingRequest, PolicyCriticRequest
from app.schemas.workflow import FixtureReviewWorkflowRequest, FixtureReviewWorkflowRun, WorkflowEvent
from app.services.review_queue import FixtureReviewQueue, ReviewQueueError
from app.services.storage import SnapshotStore


class FixtureReviewWorkflowOrchestrator:
    """Execute typed fixture decisions and persist only their real event transitions."""

    def __init__(
        self,
        store: SnapshotStore,
        queue: FixtureReviewQueue | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.store = store
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.queue = queue or FixtureReviewQueue(store, clock=self.clock)
        self.inventory_risk = InventoryRiskAgent()
        self.impact_ranking = ImpactRankingAgent()
        self.policy_critic = PolicyCriticAgent()
        self.action_drafting = ActionDraftingAgent()

    def run(self, request: FixtureReviewWorkflowRequest) -> FixtureReviewWorkflowRun:
        workflow_run_id = str(uuid4())
        events: list[WorkflowEvent] = []
        limitations: list[str] = []

        def record(
            name: str, detail: str, *evidence_refs: str, limitations: tuple[str, ...] = ()
        ) -> None:
            events.append(
                WorkflowEvent(
                    sequence=len(events) + 1,
                    name=name,  # type: ignore[arg-type]
                    occurred_at=self.clock(),
                    detail=detail,
                    evidence_refs=tuple(evidence_refs),
                    limitations=limitations,
                )
            )

        inventory_request = request.inventory_risk_request
        record("QUEUED", "Fixture specialist workflow was queued for a named evidence bundle.")
        record(
            "VALIDATING",
            "Validating fixture classification, source scope, and upstream decision statuses.",
            f"snapshot:{inventory_request.scope.snapshot_id}",
        )
        if request.data_classification != "FIXTURE" or inventory_request.data_classification != "FIXTURE":
            return self._terminal(
                workflow_run_id,
                request,
                events,
                "REJECTED",
                "Fixture workflow rejects public benchmark and retailer-classified input.",
                ("WORKFLOW_FIXTURE_ONLY",),
            )
        if request.data_contract_status == "REJECT" or request.forecast_evaluation_status == "REJECT":
            return self._terminal(
                workflow_run_id,
                request,
                events,
                "REJECTED",
                "An upstream data-contract or forecast-evaluation decision rejected the workflow.",
                ("UPSTREAM_EVIDENCE_REJECTED",),
            )
        if request.data_contract_status == "INCONCLUSIVE" or request.forecast_evaluation_status == "INCONCLUSIVE":
            return self._terminal(
                workflow_run_id,
                request,
                events,
                "INCONCLUSIVE",
                "An upstream data-contract or forecast-evaluation decision was inconclusive.",
                ("UPSTREAM_EVIDENCE_INCONCLUSIVE",),
            )
        record(
            "DATA_CONTRACT_REVIEWED",
            f"Data Contract evidence status is {request.data_contract_status}.",
            f"snapshot:{inventory_request.scope.snapshot_id}",
        )
        record(
            "FORECAST_EVALUATION_REVIEWED",
            f"Forecast Evaluation evidence status is {request.forecast_evaluation_status}.",
            f"forecast_model:{inventory_request.forecast.model_run_id}",
        )
        record(
            "FEATURES_READY",
            "The declared forecast artifact and compatible scope are available to the review path.",
            f"forecast_model:{inventory_request.forecast.model_run_id}",
            f"scope:{inventory_request.scope.scope_ref}",
        )

        risk = self.inventory_risk.decide(
            replace(
                inventory_request,
                run_id=f"{workflow_run_id}:inventory_risk",
                data_contract_status=request.data_contract_status,
                forecast_evaluation_status=request.forecast_evaluation_status,
            )
        )
        record(
            "INVENTORY_RISK_REVIEWED",
            f"Inventory Risk returned {risk.status}.",
            *self._decision_refs(risk),
            limitations=risk.agent_decision.limitations,
        )
        if risk.status == "REJECT":
            return self._terminal(
                workflow_run_id, request, events, "REJECTED", "Inventory Risk rejected the evidence.", risk.agent_decision.limitations
            )
        if risk.status == "INCONCLUSIVE" or not risk.risk_case_qualified:
            return self._terminal(
                workflow_run_id, request, events, "INCONCLUSIVE", "Inventory Risk did not qualify a review case.", risk.agent_decision.limitations
            )

        ranking = self.impact_ranking.decide(
            ImpactRankingRequest(
                run_id=f"{workflow_run_id}:impact_ranking",
                data_classification="FIXTURE",
                risk_cases=(risk,),
            )
        )
        record(
            "IMPACT_RANKING_REVIEWED",
            f"Impact Ranking returned {ranking.status}.",
            *self._decision_refs(ranking),
            limitations=ranking.agent_decision.limitations,
        )
        if ranking.status == "REJECT":
            return self._terminal(
                workflow_run_id, request, events, "REJECTED", "Impact Ranking rejected the evidence.", ranking.agent_decision.limitations
            )
        if ranking.status == "INCONCLUSIVE":
            return self._terminal(
                workflow_run_id, request, events, "INCONCLUSIVE", "Impact Ranking was inconclusive.", ranking.agent_decision.limitations
            )

        critic = self.policy_critic.decide(
            PolicyCriticRequest(
                run_id=f"{workflow_run_id}:policy_critic",
                data_classification="FIXTURE",
                data_contract_status=request.data_contract_status,
                forecast_evaluation_status=request.forecast_evaluation_status,
                inventory_risk=risk,
                impact_ranking=ranking,
            )
        )
        record(
            "POLICY_CRITIC_REVIEWED",
            f"Policy Critic returned {critic.status}.",
            *self._decision_refs(critic),
            limitations=critic.agent_decision.limitations,
        )
        if critic.status == "REJECT":
            return self._terminal(
                workflow_run_id, request, events, "REJECTED", "Policy Critic vetoed the case.", critic.agent_decision.limitations
            )
        if critic.status == "INCONCLUSIVE" or not critic.approved_for_action_draft:
            return self._terminal(
                workflow_run_id, request, events, "INCONCLUSIVE", "Policy Critic did not approve a review draft.", critic.agent_decision.limitations
            )

        action = self.action_drafting.decide(
            ActionDraftRequest(
                run_id=f"{workflow_run_id}:action_drafting",
                data_classification="FIXTURE",
                planner_owner_role=request.planner_owner_role,
                inventory_risk=risk,
                impact_ranking=ranking,
                policy_critic=critic,
            )
        )
        record(
            "ACTION_DRAFTED",
            f"Action Drafting returned {action.status}.",
            *self._decision_refs(action),
            limitations=action.agent_decision.limitations,
        )
        if action.status == "REJECT":
            return self._terminal(
                workflow_run_id, request, events, "REJECTED", "Action Drafting rejected the case.", action.agent_decision.limitations
            )
        if action.status == "INCONCLUSIVE" or action.draft is None:
            return self._terminal(
                workflow_run_id, request, events, "INCONCLUSIVE", "Action Drafting did not create a review-only draft.", action.agent_decision.limitations
            )
        try:
            case = self.queue.enqueue(
                action_draft=action,
                policy_critic=critic,
                inventory_risk=risk,
                impact_ranking=ranking,
            )
        except ReviewQueueError as error:
            return self._terminal(
                workflow_run_id,
                request,
                events,
                "FAILED",
                "The fixture queue rejected an otherwise complete local workflow.",
                (str(error),),
            )
        record(
            "REVIEW_READY",
            "Critic-approved fixture draft was persisted to the local reviewer queue.",
            f"review_case:{case.case_id}",
            f"snapshot:{risk.scope.snapshot_id}",
        )
        run = FixtureReviewWorkflowRun(
            workflow_run_id=workflow_run_id,
            created_at=events[0].occurred_at,
            data_classification="FIXTURE",
            snapshot_id=risk.scope.snapshot_id,
            status="REVIEW_READY",
            events=tuple(events),
            review_case_id=case.case_id,
        )
        self.store.persist_fixture_review_workflow_run(run)
        return run

    def _terminal(
        self,
        workflow_run_id: str,
        request: FixtureReviewWorkflowRequest,
        events: list[WorkflowEvent],
        status: str,
        detail: str,
        limitations: tuple[str, ...],
    ) -> FixtureReviewWorkflowRun:
        events.append(
            WorkflowEvent(
                sequence=len(events) + 1,
                name=status,  # type: ignore[arg-type]
                occurred_at=self.clock(),
                detail=detail,
                evidence_refs=(f"snapshot:{request.inventory_risk_request.scope.snapshot_id}",),
                limitations=limitations,
            )
        )
        run = FixtureReviewWorkflowRun(
            workflow_run_id=workflow_run_id,
            created_at=events[0].occurred_at,
            data_classification="FIXTURE",
            snapshot_id=request.inventory_risk_request.scope.snapshot_id,
            status=status,  # type: ignore[arg-type]
            events=tuple(events),
            limitations=limitations,
        )
        self.store.persist_fixture_review_workflow_run(run)
        return run

    @staticmethod
    def _decision_refs(decision: object) -> tuple[str, ...]:
        agent_decision = getattr(decision, "agent_decision")
        refs = [f"{agent_decision.agent}:{agent_decision.run_id}"]
        for finding in agent_decision.findings:
            refs.extend(finding.evidence_refs)
        return tuple(dict.fromkeys(refs))
