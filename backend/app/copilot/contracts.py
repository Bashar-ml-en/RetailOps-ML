"""Strict structured-output contracts for a public planner brief."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


PLANNER_BRIEF_SCHEMA_VERSION = "planner-brief-v1"
PLANNER_PROMPT_VERSION = "public-benchmark-planner-copilot-v1"
PUBLIC_PROHIBITED_OPERATIONS = (
    "customer_data_access",
    "inventory_risk",
    "replenishment_action",
    "external_execution",
)


class EvidenceFinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    statement: str = Field(min_length=1, max_length=500)
    evidence_refs: list[str] = Field(min_length=1, max_length=10)


class PlannerBriefProposal(BaseModel):
    """The only model-shaped result accepted before deterministic critique."""

    model_config = ConfigDict(extra="forbid")

    source_mode: Literal["PUBLIC_BENCHMARK"]
    status: Literal["PASS", "PASS_WITH_LIMITATIONS", "REJECT", "INCONCLUSIVE"]
    headline: str = Field(min_length=1, max_length=240)
    analysis_summary: str = Field(min_length=1, max_length=1_500)
    forecast_findings: list[EvidenceFinding] = Field(min_length=1, max_length=10)
    evidence_references: list[str] = Field(min_length=1, max_length=30)
    limitations: list[str] = Field(min_length=1, max_length=30)
    planner_verification_steps: list[str] = Field(min_length=1, max_length=10)
    human_decision_required: bool
    prohibited_operations: list[str] = Field(min_length=1, max_length=10)
    prompt_version: str = Field(min_length=1, max_length=100)
    model_version: str = Field(min_length=1, max_length=200)

    def to_payload(self, *, planner_brief_id: str, run_id: str) -> dict[str, object]:
        return {
            "planner_brief_schema_version": PLANNER_BRIEF_SCHEMA_VERSION,
            "planner_brief_id": planner_brief_id,
            "run_id": run_id,
            **self.model_dump(),
        }
