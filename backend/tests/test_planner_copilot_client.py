"""Provider-free tests for the bounded Responses adapter."""

import json
from dataclasses import replace
from datetime import datetime, timezone

import pytest

from app.config import settings
from app.copilot.client import CopilotResponseError, OpenAIResponsesPlannerCopilot
from app.copilot.contracts import PLANNER_PROMPT_VERSION, PUBLIC_PROHIBITED_OPERATIONS
from app.copilot.evidence import EvidenceResult, EvidenceUnavailable
from app.runtime.contracts import PublicBenchmarkScope, PublicBenchmarkSubmission
from app.runtime.store import RuntimeStore


class FakeGateway:
    def get_run_summary(self, run_id: str) -> EvidenceResult:
        return EvidenceResult((f"runtime_run:{run_id}",), {"status": "PASS_WITH_LIMITATIONS"})

    def get_forecast_evidence(self, run_id: str) -> EvidenceResult:
        return EvidenceResult(("final_test_report:report-1",), {"metrics": {"macro_average_mae": 1.0}})

    def get_limitations(self, run_id: str) -> EvidenceResult:
        return EvidenceResult((f"runtime_run:{run_id}",), {"limitations": ["PUBLIC_BENCHMARK_NOT_RETAILER_DATA"]})

    def tool_definitions(self) -> list[dict[str, object]]:
        return []

    def invoke(self, run_id: str, name: str, arguments: dict[str, object]) -> EvidenceResult:
        raise EvidenceUnavailable("UNAPPROVED_OR_WRITE_CAPABLE_TOOL")


def runtime_run(store: RuntimeStore) -> str:
    run, _ = store.enqueue(
        PublicBenchmarkSubmission(
            idempotency_key="copilot-client-test",
            selection_id="copilot-client-selection",
            scopes=tuple(PublicBenchmarkScope(101, product_id) for product_id in range(20)),
            as_of=datetime(2026, 9, 21, tzinfo=timezone.utc),
        )
    )
    return run.run_id


def enabled_config():
    return replace(
        settings,
        planner_copilot_enabled=True,
        openai_api_key="test-secret-not-a-real-key",
        planner_copilot_operator_token="test-operator-token",
        openai_model="approved-test-model",
        planner_copilot_per_run_budget_cents=20,
        planner_copilot_monthly_budget_cents=50,
        planner_copilot_no_provider_storage_approved=True,
    )


def proposal_json() -> str:
    return json.dumps(
        {
            "source_mode": "PUBLIC_BENCHMARK",
            "status": "PASS_WITH_LIMITATIONS",
            "headline": "Public benchmark evidence",
            "analysis_summary": "A bounded public report is available.",
            "forecast_findings": [
                {"statement": "Final-test evidence is available.", "evidence_refs": ["final_test_report:report-1"]}
            ],
            "evidence_references": ["runtime_run:unused", "final_test_report:report-1"],
            "limitations": ["PUBLIC_BENCHMARK_NOT_RETAILER_DATA"],
            "planner_verification_steps": ["Review limitations."],
            "human_decision_required": True,
            "prohibited_operations": list(PUBLIC_PROHIBITED_OPERATIONS),
            "prompt_version": PLANNER_PROMPT_VERSION,
            "model_version": "approved-test-model",
        }
    )


def test_adapter_rejects_model_output_that_skips_required_evidence_tools(tmp_path) -> None:
    store = RuntimeStore(tmp_path)
    run_id = runtime_run(store)

    result = OpenAIResponsesPlannerCopilot(
        runtime_store=store,
        gateway=FakeGateway(),  # type: ignore[arg-type]
        config=enabled_config(),
        sender=lambda _body, _headers: {"id": "resp-1", "output": [], "output_text": proposal_json()},
    ).create_brief(run_id)

    assert result.status == "REJECT"
    assert result.reason_code == "REQUIRED_EVIDENCE_TOOL_NOT_CALLED"
    assert store.list_planner_briefs(run_id) == []


def test_adapter_rejects_malformed_and_write_capable_tool_calls(tmp_path) -> None:
    store = RuntimeStore(tmp_path)
    run_id = runtime_run(store)

    result = OpenAIResponsesPlannerCopilot(
        runtime_store=store,
        gateway=FakeGateway(),  # type: ignore[arg-type]
        config=enabled_config(),
        sender=lambda _body, _headers: {
            "id": "resp-2",
            "output": [
                {
                    "type": "function_call",
                    "name": "create_planner_brief_draft",
                    "call_id": "call-1",
                    "arguments": "{}",
                }
            ],
        },
    ).create_brief(run_id)

    with pytest.raises(CopilotResponseError, match="COPILOT_TOOL_ARGUMENTS_MALFORMED"):
        OpenAIResponsesPlannerCopilot._arguments({"arguments": "not-json"})
    assert result.status == "REJECT"
    assert result.reason_code == "UNAPPROVED_OR_WRITE_CAPABLE_TOOL"
