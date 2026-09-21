"""Fixture-only local reviewer queue with append-only, non-executing decisions."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from uuid import uuid4

from app.schemas.review import (
    ActionDraftDecision,
    ImpactRankingDecision,
    InventoryRiskDecision,
    PlannerReviewDraft,
    PolicyCriticDecision,
    ReviewCase,
    ReviewCaseSummary,
    ReviewDecisionEvent,
    ReviewDecisionRequest,
    ReviewScope,
)
from app.services.storage import SnapshotStore


class ReviewQueueError(ValueError):
    """Raised when a local review event would break the evidence or safety boundary."""


class FixtureReviewQueue:
    """Persist local fixture review cases and decisions without any external action path."""

    def __init__(
        self, store: SnapshotStore, clock: Callable[[], datetime] | None = None
    ) -> None:
        self.store = store
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def enqueue(
        self,
        *,
        action_draft: ActionDraftDecision,
        policy_critic: PolicyCriticDecision,
        inventory_risk: InventoryRiskDecision,
        impact_ranking: ImpactRankingDecision,
    ) -> ReviewCase:
        """Store a critic-approved fixture case; public/retailer cases are rejected here."""

        classifications = {
            action_draft.data_classification,
            policy_critic.data_classification,
            inventory_risk.data_classification,
            impact_ranking.data_classification,
        }
        if classifications != {"FIXTURE"}:
            raise ReviewQueueError("REVIEW_QUEUE_FIXTURE_ONLY")
        if (
            action_draft.status not in {"PASS", "PASS_WITH_LIMITATIONS"}
            or action_draft.draft is None
            or policy_critic.status not in {"PASS", "PASS_WITH_LIMITATIONS"}
            or not policy_critic.approved_for_action_draft
        ):
            raise ReviewQueueError("POLICY_CRITIC_NOT_APPROVED")
        if not inventory_risk.risk_case_qualified or not impact_ranking.ranked_cases:
            raise ReviewQueueError("QUALIFIED_RANKED_CASE_REQUIRED")
        top_case = impact_ranking.ranked_cases[0]
        if top_case.scope != inventory_risk.scope:
            raise ReviewQueueError("REVIEW_CASE_SCOPE_MISMATCH")
        if action_draft.draft.external_execution_permitted:
            raise ReviewQueueError("EXTERNAL_EXECUTION_PROHIBITED")
        case = ReviewCase(
            case_id=str(uuid4()),
            created_at=self.clock(),
            data_classification="FIXTURE",
            scope=inventory_risk.scope,
            planner_owner_role=action_draft.draft.planner_owner_role,
            draft=action_draft.draft,
            policy_critic_run_id=policy_critic.agent_decision.run_id,
            evidence_refs=(
                f"action_draft:{action_draft.agent_decision.run_id}",
                f"policy_critic:{policy_critic.agent_decision.run_id}",
                f"impact_ranking:{impact_ranking.agent_decision.run_id}",
                f"inventory_risk:{inventory_risk.agent_decision.run_id}",
                f"snapshot:{inventory_risk.scope.snapshot_id}",
            ),
        )
        self.store.persist_review_case(case)
        return case

    def record_decision(self, request: ReviewDecisionRequest) -> ReviewDecisionEvent:
        """Append a planner decision; approval is auditable but has no execution effect."""

        summary = self.get_case(request.case_id)
        if summary is None:
            raise ReviewQueueError("REVIEW_CASE_NOT_FOUND")
        if request.planner_owner_role != summary.case.planner_owner_role:
            raise ReviewQueueError("PLANNER_ROLE_MISMATCH")
        if summary.state in {"APPROVED", "DECLINED"}:
            raise ReviewQueueError("REVIEW_CASE_ALREADY_TERMINAL")
        decision = ReviewDecisionEvent(
            decision_id=str(uuid4()),
            case_id=request.case_id,
            recorded_at=self.clock(),
            planner_owner_role=request.planner_owner_role,
            outcome=request.outcome,
            reason=request.reason,
        )
        self.store.persist_review_decision(decision)
        return decision

    def get_case(self, case_id: str) -> ReviewCaseSummary | None:
        payload = self.store.load_review_case(case_id)
        if payload is None:
            return None
        case = self._case_from_payload(payload)
        decisions = tuple(
            self._decision_from_payload(item) for item in self.store.list_review_decisions(case_id)
        )
        state = "READY_FOR_REVIEW" if not decisions else {
            "DEFER": "DEFERRED",
            "APPROVE": "APPROVED",
            "DECLINE": "DECLINED",
        }[decisions[-1].outcome]
        return ReviewCaseSummary(case=case, state=state, decisions=decisions)  # type: ignore[arg-type]

    def list_cases(self) -> tuple[ReviewCaseSummary, ...]:
        summaries = [
            self.get_case(str(payload["case_id"]))
            for payload in self.store.list_review_cases()
        ]
        return tuple(summary for summary in summaries if summary is not None)

    @staticmethod
    def _timestamp(value: object, field: str) -> datetime:
        if not isinstance(value, str):
            raise ReviewQueueError(f"REVIEW_QUEUE_RECORD_MALFORMED:{field}")
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError as error:
            raise ReviewQueueError(f"REVIEW_QUEUE_RECORD_MALFORMED:{field}") from error
        if parsed.tzinfo is None:
            raise ReviewQueueError(f"REVIEW_QUEUE_RECORD_MALFORMED:{field}")
        return parsed

    @staticmethod
    def _mapping(payload: Mapping[str, object], field: str) -> dict[str, object]:
        value = payload.get(field)
        if not isinstance(value, dict):
            raise ReviewQueueError(f"REVIEW_QUEUE_RECORD_MALFORMED:{field}")
        return value

    def _case_from_payload(self, payload: Mapping[str, object]) -> ReviewCase:
        scope_payload = self._mapping(payload, "scope")
        draft_payload = self._mapping(payload, "draft")
        try:
            scope = ReviewScope(
                tenant_id=str(scope_payload["tenant_id"]),
                snapshot_id=str(scope_payload["snapshot_id"]),
                sku=str(scope_payload["sku"]),
                location_id=str(scope_payload["location_id"]),
                quantity_unit=str(scope_payload["quantity_unit"]),
            )
            draft = PlannerReviewDraft(
                case_id=str(draft_payload["case_id"]),
                planner_owner_role=str(draft_payload["planner_owner_role"]),
                summary=str(draft_payload["summary"]),
                requested_human_decision=str(draft_payload["requested_human_decision"]),  # type: ignore[arg-type]
                external_execution_permitted=bool(draft_payload["external_execution_permitted"]),  # type: ignore[arg-type]
            )
            evidence_refs = tuple(str(item) for item in payload["evidence_refs"])
            return ReviewCase(
                case_id=str(payload["case_id"]),
                created_at=self._timestamp(payload.get("created_at"), "created_at"),
                data_classification=str(payload["data_classification"]),  # type: ignore[arg-type]
                scope=scope,
                planner_owner_role=str(payload["planner_owner_role"]),
                draft=draft,
                policy_critic_run_id=str(payload["policy_critic_run_id"]),
                evidence_refs=evidence_refs,
            )
        except (KeyError, TypeError, ValueError) as error:
            raise ReviewQueueError("REVIEW_QUEUE_RECORD_MALFORMED:case") from error

    def _decision_from_payload(self, payload: Mapping[str, object]) -> ReviewDecisionEvent:
        try:
            return ReviewDecisionEvent(
                decision_id=str(payload["decision_id"]),
                case_id=str(payload["case_id"]),
                recorded_at=self._timestamp(payload.get("recorded_at"), "recorded_at"),
                planner_owner_role=str(payload["planner_owner_role"]),
                outcome=str(payload["outcome"]),  # type: ignore[arg-type]
                reason=str(payload["reason"]),
                external_execution_permitted=bool(payload["external_execution_permitted"]),  # type: ignore[arg-type]
            )
        except (KeyError, TypeError, ValueError) as error:
            raise ReviewQueueError("REVIEW_QUEUE_RECORD_MALFORMED:decision") from error
