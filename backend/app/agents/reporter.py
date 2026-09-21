"""Deterministic Action Drafting Agent for human-review text only."""

from app.agents.contracts import AgentDecision, EvidenceFinding
from app.schemas.review import ActionDraftDecision, ActionDraftRequest, PlannerReviewDraft


class ActionDraftingAgent:
    """Create a review-only draft after a critic pass; never issue an operation."""

    name = "action_drafting"

    def decide(self, request: ActionDraftRequest) -> ActionDraftDecision:
        critic = request.policy_critic
        if request.data_classification == "PUBLIC_BENCHMARK":
            return self._decision(
                request,
                status="REJECT",
                limitations=("PUBLIC_BENCHMARK_ACTION_DRAFT_BLOCKED",),
                next_action="use_authorised_retailer_evidence",
                statement="Public benchmark evidence cannot generate a planner review draft.",
            )
        if critic.status not in {"PASS", "PASS_WITH_LIMITATIONS"} or not critic.approved_for_action_draft:
            return self._decision(
                request,
                status="INCONCLUSIVE",
                limitations=("POLICY_CRITIC_NOT_APPROVED",),
                next_action="resolve_policy_critic_limitations",
                statement="No draft is created until the Policy Critic approves the complete evidence chain.",
            )
        if not request.impact_ranking.ranked_cases or not request.inventory_risk.risk_case_qualified:
            return self._decision(
                request,
                status="INCONCLUSIVE",
                limitations=("QUALIFIED_CASE_MISSING",),
                next_action="complete_inventory_and_ranking_evidence",
                statement="No draft is created without a qualified, ranked review case.",
            )
        top_case = request.impact_ranking.ranked_cases[0]
        fixture_limited = request.data_classification == "FIXTURE"
        summary = (
            f"Review {top_case.scope.sku} at {top_case.scope.location_id}: declared forecast and "
            "confirmed supply evidence indicate a shortfall during the recorded lead time. "
            "Confirm source freshness and decide whether to approve, decline, or defer this review case."
        )
        draft = PlannerReviewDraft(
            case_id=f"review:{request.run_id}:{top_case.scope.scope_ref}",
            planner_owner_role=request.planner_owner_role,
            summary=summary,
        )
        limitations = ("FIXTURE_ONLY_NOT_OPERATIONAL",) if fixture_limited else ()
        return ActionDraftDecision(
            agent_decision=AgentDecision(
                agent=self.name,
                run_id=request.run_id,
                status="PASS_WITH_LIMITATIONS" if fixture_limited else "PASS",
                findings=(
                    EvidenceFinding(
                        statement="A critic-approved human-review draft was created with no external execution authority.",
                        evidence_refs=(
                            f"policy_critic:{critic.agent_decision.run_id}",
                            f"impact_ranking:{request.impact_ranking.agent_decision.run_id}",
                            f"inventory_risk:{request.inventory_risk.agent_decision.run_id}",
                        ),
                    ),
                ),
                limitations=limitations,
                next_action="enqueue_fixture_review_case",
            ),
            data_classification=request.data_classification,
            draft=draft,
            limitations=limitations,
        )

    def _decision(
        self,
        request: ActionDraftRequest,
        *,
        status: str,
        limitations: tuple[str, ...],
        next_action: str,
        statement: str,
    ) -> ActionDraftDecision:
        return ActionDraftDecision(
            agent_decision=AgentDecision(
                agent=self.name,
                run_id=request.run_id,
                status=status,  # type: ignore[arg-type]
                findings=(EvidenceFinding(statement=statement),),
                limitations=limitations,
                next_action=next_action,
            ),
            data_classification=request.data_classification,
            limitations=limitations,
        )
