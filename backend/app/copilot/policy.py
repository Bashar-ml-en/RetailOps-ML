"""Deterministic post-model policy gate for public planner briefs."""

from __future__ import annotations

import re
from dataclasses import dataclass
from uuid import uuid4

from app.copilot.contracts import (
    PLANNER_PROMPT_VERSION,
    PUBLIC_PROHIBITED_OPERATIONS,
    PlannerBriefProposal,
)
from app.copilot.evidence import PublicBenchmarkEvidenceGateway


FORBIDDEN_ACTION_LANGUAGE = re.compile(
    r"\b(purchase|buy stock|transfer inventory|change price|contact supplier|place order)\b",
    re.IGNORECASE,
)
PROMPT_INJECTION_LANGUAGE = re.compile(
    r"\b(ignore (all |any |the )?(previous|prior) instructions|system prompt|developer message)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class PolicyDecision:
    status: str
    reason_code: str | None
    payload: dict[str, object] | None


class PlannerBriefPolicy:
    """Fail closed unless a proposal exactly matches persisted public evidence."""

    def validate(
        self,
        *,
        run_id: str,
        proposal: PlannerBriefProposal,
        gateway: PublicBenchmarkEvidenceGateway,
    ) -> PolicyDecision:
        try:
            summary = gateway.get_run_summary(run_id)
            forecast = gateway.get_forecast_evidence(run_id)
            limitations = gateway.get_limitations(run_id)
        except ValueError as error:
            return PolicyDecision("INCONCLUSIVE", str(error), None)
        if proposal.prompt_version != PLANNER_PROMPT_VERSION:
            return PolicyDecision("REJECT", "PROMPT_VERSION_MISMATCH", None)
        if proposal.source_mode != "PUBLIC_BENCHMARK":
            return PolicyDecision("REJECT", "SOURCE_MODE_MISMATCH", None)
        expected_status = summary.payload.get("status")
        if proposal.status != expected_status:
            return PolicyDecision("REJECT", "STATUS_NOT_SUPPORTED_BY_EVIDENCE", None)
        evidence_refs = set(summary.evidence_refs + forecast.evidence_refs + limitations.evidence_refs)
        cited_refs = set(proposal.evidence_references)
        finding_refs = {ref for finding in proposal.forecast_findings for ref in finding.evidence_refs}
        if not cited_refs or not finding_refs or not (cited_refs | finding_refs).issubset(evidence_refs):
            return PolicyDecision("REJECT", "UNSUPPORTED_EVIDENCE_REFERENCE", None)
        if set(proposal.limitations) - set(limitations.payload["limitations"]):
            return PolicyDecision("REJECT", "UNSUPPORTED_LIMITATION", None)
        if not proposal.human_decision_required:
            return PolicyDecision("REJECT", "HUMAN_VERIFICATION_REQUIRED", None)
        if not set(PUBLIC_PROHIBITED_OPERATIONS).issubset(proposal.prohibited_operations):
            return PolicyDecision("REJECT", "PUBLIC_OPERATION_BOUNDARY_MISSING", None)
        text = " ".join(
            [proposal.headline, proposal.analysis_summary]
            + [finding.statement for finding in proposal.forecast_findings]
            + proposal.planner_verification_steps
        )
        if FORBIDDEN_ACTION_LANGUAGE.search(text):
            return PolicyDecision("REJECT", "FORBIDDEN_OPERATION_LANGUAGE", None)
        if PROMPT_INJECTION_LANGUAGE.search(text):
            return PolicyDecision("REJECT", "PROMPT_INJECTION_LANGUAGE", None)
        return PolicyDecision(
            "PASS_WITH_LIMITATIONS",
            None,
            proposal.to_payload(planner_brief_id=str(uuid4()), run_id=run_id),
        )
