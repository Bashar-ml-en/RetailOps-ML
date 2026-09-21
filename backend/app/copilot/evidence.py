"""Tenant-safe, compact evidence tools for one public benchmark run."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from app.runtime.contracts import RuntimeStatus
from app.runtime.store import RuntimeStore
from app.services.storage import SnapshotStore


class EvidenceUnavailable(ValueError):
    """Raised when a tool would exceed its approved public evidence boundary."""


@dataclass(frozen=True)
class EvidenceResult:
    evidence_refs: tuple[str, ...]
    payload: dict[str, object]


class PublicBenchmarkEvidenceGateway:
    """Expose allowlisted summaries only; raw public rows never leave storage."""

    def __init__(self, runtime_store: RuntimeStore, *, audit_root: Path) -> None:
        self.runtime_store = runtime_store
        self.artifact_store = SnapshotStore(audit_root)

    def get_run_summary(self, run_id: str) -> EvidenceResult:
        run = self._ready_run(run_id)
        outcome = run.outcome or {}
        return EvidenceResult(
            evidence_refs=(f"runtime_run:{run_id}",),
            payload={
                "run_id": run_id,
                "source_mode": "PUBLIC_BENCHMARK",
                "status": outcome.get("status"),
                "selection": outcome.get("selection"),
                "selected_model_version": outcome.get("selected_model_version"),
                "metrics": outcome.get("metrics"),
                "limitations": outcome.get("limitations", []),
                "next_action": outcome.get("next_action"),
            },
        )

    def get_forecast_evidence(self, run_id: str, scope_ref: str | None = None) -> EvidenceResult:
        run = self._ready_run(run_id)
        report_id = str((run.outcome or {}).get("final_test_report_id", ""))
        report = self.artifact_store.load_public_benchmark_final_test_report(report_id)
        if report is None:
            raise EvidenceUnavailable("FINAL_TEST_REPORT_NOT_FOUND")
        final_test = report.get("final_test")
        if not isinstance(final_test, dict):
            raise EvidenceUnavailable("FINAL_TEST_REPORT_MALFORMED")
        if scope_ref is None:
            return EvidenceResult(
                evidence_refs=(f"final_test_report:{report_id}",),
                payload={
                    "report_id": report_id,
                    "selection": report.get("selection"),
                    "metrics": final_test.get("metrics"),
                    "limitations": report.get("limitations", []),
                    "prohibited_claims": report.get("prohibited_claims", []),
                },
            )
        evaluations = final_test.get("evaluations")
        if not isinstance(evaluations, list):
            raise EvidenceUnavailable("FINAL_TEST_REPORT_MALFORMED")
        for evaluation in evaluations:
            if not isinstance(evaluation, dict):
                continue
            found_ref = (
                f"sku:{evaluation.get('sku')}|location:{evaluation.get('location_id')}|"
                f"unit:{evaluation.get('quantity_unit')}"
            )
            if found_ref == scope_ref:
                return EvidenceResult(
                    evidence_refs=(f"final_test_report:{report_id}", f"scope:{scope_ref}"),
                    payload={"report_id": report_id, "scope_ref": scope_ref, "final_test": evaluation},
                )
        raise EvidenceUnavailable("PUBLIC_BENCHMARK_SCOPE_NOT_FOUND")

    def get_limitations(self, run_id: str) -> EvidenceResult:
        run = self._ready_run(run_id)
        limitations = list((run.outcome or {}).get("limitations", []))
        return EvidenceResult(
            evidence_refs=(f"runtime_run:{run_id}",),
            payload={"run_id": run_id, "limitations": limitations},
        )

    def get_qualified_cases(self, run_id: str) -> EvidenceResult:
        self._ready_run(run_id)
        return EvidenceResult(
            evidence_refs=(f"runtime_run:{run_id}",),
            payload={
                "qualified_cases": [],
                "limitations": [
                    "PUBLIC_BENCHMARK_HAS_NO_AUTHORISED_INVENTORY_OR_ACTION_CASES"
                ],
            },
        )

    def invoke(self, run_id: str, name: str, arguments: dict[str, object]) -> EvidenceResult:
        """Invoke an allowlisted, run-bound tool; callers cannot select another run."""

        handlers: dict[str, Callable[[], EvidenceResult]] = {
            "get_run_summary": lambda: self.get_run_summary(run_id),
            "get_forecast_evidence": lambda: self.get_forecast_evidence(
                run_id, self._optional_scope(arguments)
            ),
            "get_limitations": lambda: self.get_limitations(run_id),
            "get_qualified_cases": lambda: self.get_qualified_cases(run_id),
        }
        try:
            return handlers[name]()
        except KeyError as error:
            raise EvidenceUnavailable("UNAPPROVED_OR_WRITE_CAPABLE_TOOL") from error

    @staticmethod
    def tool_definitions() -> list[dict[str, object]]:
        """Responses API-compatible custom function definitions with no write tool."""

        empty_parameters = {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        }
        return [
            {
                "type": "function",
                "name": "get_run_summary",
                "description": "Read the compact persisted summary for the bound public benchmark run.",
                "parameters": empty_parameters,
                "strict": True,
            },
            {
                "type": "function",
                "name": "get_forecast_evidence",
                "description": "Read final-test evidence for the bound run, optionally for one known scope reference.",
                "parameters": {
                    "type": "object",
                    "properties": {"scope_ref": {"type": "string", "maxLength": 200}},
                    "additionalProperties": False,
                },
                "strict": True,
            },
            {
                "type": "function",
                "name": "get_limitations",
                "description": "Read the persisted limitations for the bound public benchmark run.",
                "parameters": empty_parameters,
                "strict": True,
            },
            {
                "type": "function",
                "name": "get_qualified_cases",
                "description": "Confirm that public benchmark runs have no inventory or action cases.",
                "parameters": empty_parameters,
                "strict": True,
            },
        ]

    def _ready_run(self, run_id: str):
        run = self.runtime_store.get_run(run_id)
        if run is None:
            raise EvidenceUnavailable("PUBLIC_BENCHMARK_RUN_NOT_FOUND")
        if run.status is not RuntimeStatus.REPORT_READY:
            raise EvidenceUnavailable("PUBLIC_BENCHMARK_REPORT_NOT_READY")
        return run

    @staticmethod
    def _optional_scope(arguments: dict[str, object]) -> str | None:
        value = arguments.get("scope_ref")
        if value is None:
            return None
        if not isinstance(value, str) or not value.strip() or len(value) > 200:
            raise EvidenceUnavailable("INVALID_SCOPE_REFERENCE")
        return value
