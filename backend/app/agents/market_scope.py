"""Deterministic, non-financial Impact Ranking Agent for qualified cases."""

from app.agents.contracts import AgentDecision, EvidenceFinding
from app.schemas.review import (
    ImpactRankingDecision,
    ImpactRankingRequest,
    RankedReviewCase,
)


class ImpactRankingAgent:
    """Rank only qualified risk cases; never infer profit, revenue, or availability."""

    name = "impact_ranking"

    def decide(self, request: ImpactRankingRequest) -> ImpactRankingDecision:
        if request.data_classification == "PUBLIC_BENCHMARK":
            return self._decision(
                request,
                status="INCONCLUSIVE",
                limitations=("PUBLIC_BENCHMARK_IMPACT_RANKING_BLOCKED",),
                next_action="use_authorised_inventory_risk_case",
                statement="Public benchmark data cannot support an operational impact ranking.",
            )
        if not request.risk_cases:
            return self._decision(
                request,
                status="INCONCLUSIVE",
                limitations=("NO_QUALIFIED_RISK_CASE",),
                next_action="qualify_inventory_risk_case",
                statement="Impact ranking requires at least one qualified inventory-risk case.",
            )
        incomplete = [case for case in request.risk_cases if case.status not in {"PASS", "PASS_WITH_LIMITATIONS"} or not case.risk_case_qualified]
        if incomplete:
            return self._decision(
                request,
                status="INCONCLUSIVE",
                limitations=("RISK_CASE_NOT_QUALIFIED",),
                next_action="complete_inventory_risk_evidence",
                statement="Every ranked case must first pass the deterministic inventory-risk gate.",
            )
        if any(case.data_classification != request.data_classification for case in request.risk_cases):
            return self._decision(
                request,
                status="REJECT",
                limitations=("MIXED_DATA_CLASSIFICATION",),
                next_action="separate_cases_by_data_classification",
                statement="Cases from different source classifications cannot be ranked together.",
            )
        ordered = sorted(
            request.risk_cases,
            key=lambda case: (
                -(case.shortfall_quantity or 0.0),
                case.coverage_days if case.coverage_days is not None else float("inf"),
                case.scope.scope_ref,
            ),
        )
        ranked_cases = tuple(
            RankedReviewCase(
                rank=index,
                scope=case.scope,
                shortfall_quantity=case.shortfall_quantity or 0.0,
                coverage_days=case.coverage_days or 0.0,
                evidence_refs=(
                    f"inventory_risk:{case.agent_decision.run_id}",
                    f"snapshot:{case.scope.snapshot_id}",
                    f"forecast:{case.scope.scope_ref}",
                ),
            )
            for index, case in enumerate(ordered, start=1)
        )
        status = "PASS_WITH_LIMITATIONS" if request.data_classification == "FIXTURE" else "PASS"
        limitations = ("FIXTURE_ONLY_NOT_OPERATIONAL",) if status == "PASS_WITH_LIMITATIONS" else ()
        return ImpactRankingDecision(
            agent_decision=AgentDecision(
                agent=self.name,
                run_id=request.run_id,
                status=status,  # type: ignore[arg-type]
                findings=(
                    EvidenceFinding(
                        statement=(
                            "Qualified review cases were ordered by declared shortfall, then lower "
                            "coverage; no revenue or profit claim was calculated."
                        ),
                        evidence_refs=tuple(
                            f"inventory_risk:{case.agent_decision.run_id}" for case in ordered
                        ),
                    ),
                ),
                limitations=limitations,
                next_action="policy_critic_review",
            ),
            data_classification=request.data_classification,
            ranking_policy_version=request.ranking_policy_version,
            ranked_cases=ranked_cases,
        )

    def _decision(
        self,
        request: ImpactRankingRequest,
        *,
        status: str,
        limitations: tuple[str, ...],
        next_action: str,
        statement: str,
    ) -> ImpactRankingDecision:
        return ImpactRankingDecision(
            agent_decision=AgentDecision(
                agent=self.name,
                run_id=request.run_id,
                status=status,  # type: ignore[arg-type]
                findings=(EvidenceFinding(statement=statement),),
                limitations=limitations,
                next_action=next_action,
            ),
            data_classification=request.data_classification,
            ranking_policy_version=request.ranking_policy_version,
        )
