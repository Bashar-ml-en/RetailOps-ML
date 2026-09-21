"""Deterministic Policy Critic for review cases; it has veto authority."""

from app.agents.contracts import AgentDecision, EvidenceFinding
from app.schemas.review import PolicyCriticDecision, PolicyCriticRequest


class PolicyCriticAgent:
    """Reject unsafe claims and block drafts until all required evidence passes."""

    name = "policy_critic"

    def decide(self, request: PolicyCriticRequest) -> PolicyCriticDecision:
        evidence_refs = (
            f"inventory_risk:{request.inventory_risk.agent_decision.run_id}",
            f"impact_ranking:{request.impact_ranking.agent_decision.run_id}",
        )
        if request.data_classification == "PUBLIC_BENCHMARK":
            return self._decision(
                request,
                status="REJECT",
                limitations=("PUBLIC_BENCHMARK_ACTION_DRAFT_BLOCKED",),
                next_action="use_authorised_retailer_evidence",
                statement="Public benchmark evidence cannot enter a retail review or action-drafting flow.",
                evidence_refs=evidence_refs,
            )
        if request.requested_action != "HUMAN_REVIEW":
            return self._decision(
                request,
                status="REJECT",
                limitations=("EXTERNAL_OPERATION_PROHIBITED",),
                next_action="replace_with_human_review_only",
                statement="RetailOps may draft a human review only; external operational execution is prohibited.",
                evidence_refs=evidence_refs,
            )
        upstream_statuses = (
            request.data_contract_status,
            request.forecast_evaluation_status,
            request.inventory_risk.status,
            request.impact_ranking.status,
        )
        if "REJECT" in upstream_statuses:
            return self._decision(
                request,
                status="REJECT",
                limitations=("UPSTREAM_EVIDENCE_REJECTED",),
                next_action="correct_rejected_evidence",
                statement="A required upstream decision rejected the case, so the critic vetoed it.",
                evidence_refs=evidence_refs,
            )
        if "INCONCLUSIVE" in upstream_statuses or not request.inventory_risk.risk_case_qualified:
            return self._decision(
                request,
                status="INCONCLUSIVE",
                limitations=("UPSTREAM_EVIDENCE_INCOMPLETE",),
                next_action="supply_complete_inventory_and_lead_time_evidence",
                statement="The case lacks a qualified, complete evidence chain for human review.",
                evidence_refs=evidence_refs,
            )
        if not request.impact_ranking.ranked_cases:
            return self._decision(
                request,
                status="INCONCLUSIVE",
                limitations=("RISK_CASE_NOT_RANKED",),
                next_action="rank_qualified_case",
                statement="A qualified case must have an inspectable non-financial priority before review.",
                evidence_refs=evidence_refs,
            )
        status = "PASS_WITH_LIMITATIONS" if request.data_classification == "FIXTURE" else "PASS"
        limitations = ("FIXTURE_ONLY_NOT_OPERATIONAL",) if status == "PASS_WITH_LIMITATIONS" else ()
        return self._decision(
            request,
            status=status,
            limitations=limitations,
            next_action="draft_human_review",
            statement="The evidence supports a human-review draft only; no external action is authorised.",
            evidence_refs=evidence_refs,
            approved=True,
        )

    def _decision(
        self,
        request: PolicyCriticRequest,
        *,
        status: str,
        limitations: tuple[str, ...],
        next_action: str,
        statement: str,
        evidence_refs: tuple[str, ...],
        approved: bool = False,
    ) -> PolicyCriticDecision:
        return PolicyCriticDecision(
            agent_decision=AgentDecision(
                agent=self.name,
                run_id=request.run_id,
                status=status,  # type: ignore[arg-type]
                findings=(EvidenceFinding(statement=statement, evidence_refs=evidence_refs),),
                limitations=limitations,
                next_action=next_action,
            ),
            data_classification=request.data_classification,
            approved_for_action_draft=approved,
        )
