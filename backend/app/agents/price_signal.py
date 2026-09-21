"""Deterministic Forecast Evaluation Agent for recorded forecast artifacts."""

from app.agents.contracts import AgentDecision, EvidenceFinding
from app.schemas.benchmark import FreshRetailNetFinalTestReport
from app.schemas.forecast import BaselineRun, ModelLifecycleRun


class ForecastEvaluationAgent:
    """Return typed lifecycle decisions from recorded baseline artifacts only."""

    name = "forecast_evaluation"

    def decide(
        self, run: BaselineRun | ModelLifecycleRun | FreshRetailNetFinalTestReport
    ) -> AgentDecision:
        if isinstance(run, FreshRetailNetFinalTestReport):
            return self._decide_final_test(run)
        if isinstance(run, ModelLifecycleRun):
            return self._decide_lifecycle(run)
        return self._decide_baseline(run)

    def _decide_baseline(self, run: BaselineRun) -> AgentDecision:
        finding = EvidenceFinding(
            statement="The declared naïve baseline was evaluated only on chronological validation; the final test partition remains locked.",
            evidence_refs=(
                f"baseline_run:{run.run_id}",
                f"snapshot:{run.request.snapshot_id}",
                f"feature:{run.feature_hash or 'unavailable'}",
            ),
        )
        next_action = "register_baseline" if run.status in {"PASS", "PASS_WITH_LIMITATIONS"} else "request_eligible_history"
        return AgentDecision(
            agent=self.name,
            run_id=run.run_id,
            status=run.status,
            findings=(finding,),
            limitations=run.limitations,
            next_action=next_action,
        )

    def _decide_lifecycle(self, run: ModelLifecycleRun) -> AgentDecision:
        finding = EvidenceFinding(
            statement=(
                "The fixed candidate was compared with the recorded naïve baseline only on "
                "chronological validation; the final test partition remains locked."
            ),
            evidence_refs=(
                f"model_run:{run.model_run_id}",
                f"baseline_run:{run.request.baseline_run_id}",
                f"snapshot:{run.request.snapshot_id}",
                f"feature:{run.feature_hash or 'unavailable'}",
            ),
        )
        if run.selection == "PROMOTED_CANDIDATE":
            next_action = "register_local_candidate_champion"
        elif run.selection == "RETAINED_BASELINE":
            next_action = "retain_registered_baseline"
        else:
            next_action = run.next_action
        return AgentDecision(
            agent=self.name,
            run_id=run.model_run_id,
            status=run.status,
            findings=(finding,),
            limitations=run.limitations,
            next_action=next_action,
        )

    def _decide_final_test(self, report: FreshRetailNetFinalTestReport) -> AgentDecision:
        finding = EvidenceFinding(
            statement=(
                "The validation-selected model was evaluated once on the locked public "
                "benchmark final test; this report did not alter model selection."
            ),
            evidence_refs=(
                f"final_test_report:{report.report_id}",
                f"model_run:{report.model_run_id}",
                f"baseline_run:{report.baseline_run_id}",
                f"snapshot:{report.snapshot_id}",
            ),
        )
        return AgentDecision(
            agent=self.name,
            run_id=report.report_id,
            status=report.status,
            findings=(finding,),
            limitations=report.limitations,
            next_action="retain_public_benchmark_report_only",
        )
