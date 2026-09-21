"""Separate local worker for the public FreshRetailNet benchmark runtime."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from uuid import uuid4

from app.config import settings
from app.runtime.contracts import RuntimeEventName, RuntimeRun, RuntimeStatus
from app.runtime.store import RuntimeStore
from app.schemas.benchmark import FreshRetailNetBenchmarkRequest, FreshRetailNetScope
from app.schemas.forecast import BaselineRunRequest, ModelLifecycleRequest
from app.services.final_test import FinalTestReportError, PublicBenchmarkFinalTestReporter
from app.services.forecasting import BaselineRunner
from app.services.freshretailnet import FreshRetailNetBenchmarkRunner, FreshRetailNetMappingError
from app.services.model_lifecycle import ModelLifecycleRunner
from app.services.storage import SnapshotStore


class PublicBenchmarkWorker:
    """Claim and execute one public-only run using the existing lifecycle services.

    The worker does not fetch data, own a schedule, accept a tenant, or execute
    operations. Its only source is a server-configured local parquet path whose
    provenance is recorded by the FreshRetailNet adapter.
    """

    def __init__(
        self,
        runtime_store: RuntimeStore,
        *,
        audit_root: Path,
        source_path: Path | None,
        worker_id: str | None = None,
    ) -> None:
        self.runtime_store = runtime_store
        self.audit_root = audit_root
        self.source_path = source_path
        self.worker_id = worker_id or f"local-public-worker-{uuid4()}"

    def run_once(self) -> RuntimeRun | None:
        """Claim and process one run; returns ``None`` when no work is queued."""

        run = self.runtime_store.claim_next(self.worker_id)
        if run is None:
            return None
        return self._execute(run)

    def _execute(self, run: RuntimeRun) -> RuntimeRun:
        if self.source_path is None:
            return self.runtime_store.finish(
                run.run_id,
                RuntimeStatus.INCONCLUSIVE,
                RuntimeEventName.INCONCLUSIVE,
                "No server-side public benchmark source is configured.",
                {
                    "reason_code": "PUBLIC_BENCHMARK_SOURCE_NOT_CONFIGURED",
                    "limitations": ["PUBLIC_BENCHMARK_SOURCE_NOT_CONFIGURED"],
                    "next_action": "configure_server_side_public_benchmark_source",
                },
            )
        if not self.source_path.is_file():
            return self.runtime_store.finish(
                run.run_id,
                RuntimeStatus.INCONCLUSIVE,
                RuntimeEventName.INCONCLUSIVE,
                "Configured public benchmark source is unavailable to the worker.",
                {
                    "reason_code": "PUBLIC_BENCHMARK_SOURCE_FILE_NOT_FOUND",
                    "limitations": ["PUBLIC_BENCHMARK_SOURCE_FILE_NOT_FOUND"],
                    "next_action": "restore_configured_public_benchmark_source",
                },
            )

        request = FreshRetailNetBenchmarkRequest(
            selection_id=run.submission.selection_id,
            scopes=tuple(
                FreshRetailNetScope(store_id=scope.store_id, product_id=scope.product_id)
                for scope in run.submission.scopes
            ),
            as_of=run.submission.as_of,
        )
        store = SnapshotStore(self.audit_root)
        try:
            self.runtime_store.record_progress(
                run.run_id,
                RuntimeEventName.VALIDATING,
                "Validating the configured public source against the pinned FreshRetailNet contract.",
            )
            materialization = FreshRetailNetBenchmarkRunner.for_root(self.audit_root).run_from_parquet(
                request, self.source_path
            )
            benchmark_run = materialization.run
            self.runtime_store.record_progress(
                run.run_id,
                RuntimeEventName.SNAPSHOT_STORED,
                "Immutable public benchmark snapshot stored.",
                f"snapshot:{benchmark_run.manifest.snapshot_id}",
                f"benchmark_run:{benchmark_run.run_id}",
            )

            baseline = BaselineRunner().run(
                BaselineRunRequest(
                    tenant_id=benchmark_run.manifest.tenant_id,
                    snapshot_id=benchmark_run.manifest.snapshot_id,
                    operating_timezone="UTC",
                ),
                manifest=benchmark_run.manifest,
                data_contract=benchmark_run.result,
                bundle=materialization.bundle,
            )
            store.persist_baseline_run(baseline)
            self.runtime_store.record_progress(
                run.run_id,
                RuntimeEventName.BASELINE_EVALUATED,
                "Chronology-safe baseline evaluation persisted; locked final days were excluded from selection.",
                f"baseline_run:{baseline.run_id}",
                f"feature:{baseline.feature_version}",
            )

            lifecycle = ModelLifecycleRunner().run(
                ModelLifecycleRequest(
                    tenant_id=benchmark_run.manifest.tenant_id,
                    snapshot_id=benchmark_run.manifest.snapshot_id,
                    baseline_run_id=baseline.run_id,
                ),
                manifest=benchmark_run.manifest,
                data_contract=benchmark_run.result,
                baseline_run=baseline,
                bundle=materialization.bundle,
            )
            store.persist_model_run(lifecycle)
            self.runtime_store.record_progress(
                run.run_id,
                RuntimeEventName.MODEL_SELECTED,
                "Fixed candidate was compared with the declared baseline on validation only.",
                f"model_run:{lifecycle.model_run_id}",
                f"selected_model:{lifecycle.selected_model_version}",
            )

            report = PublicBenchmarkFinalTestReporter.for_root(self.audit_root).evaluate_and_persist(
                benchmark_run_id=benchmark_run.run_id,
                baseline_run_id=baseline.run_id,
                model_run_id=lifecycle.model_run_id,
            )
            self.runtime_store.record_progress(
                run.run_id,
                RuntimeEventName.FINAL_TEST_REPORTED,
                "The locked final test was reported after the validation selection and did not change it.",
                f"final_test_report:{report.report_id}",
            )
            return self.runtime_store.finish(
                run.run_id,
                RuntimeStatus.REPORT_READY,
                RuntimeEventName.REPORT_READY,
                "Public benchmark forecast report is ready for human review; inventory and action claims remain blocked.",
                {
                    "benchmark_run_id": benchmark_run.run_id,
                    "snapshot_id": benchmark_run.manifest.snapshot_id,
                    "baseline_run_id": baseline.run_id,
                    "model_run_id": lifecycle.model_run_id,
                    "final_test_report_id": report.report_id,
                    "status": report.status,
                    "selection": report.selection,
                    "selected_model_version": report.selected_model_version,
                    "metrics": report.to_dict()["final_test"]["metrics"],
                    "limitations": list(report.limitations),
                    "next_action": "review_labelled_public_benchmark_report",
                },
                f"final_test_report:{report.report_id}",
            )
        except FreshRetailNetMappingError as error:
            return self._finish_mapping_failure(run, str(error))
        except FinalTestReportError as error:
            return self.runtime_store.finish(
                run.run_id,
                RuntimeStatus.FAILED,
                RuntimeEventName.FAILED,
                "The persisted artifact chain could not produce a final-test report safely.",
                {
                    "reason_code": str(error),
                    "limitations": [str(error)],
                    "next_action": "inspect_persisted_public_benchmark_artifact_chain",
                },
            )
        except ValueError as error:
            return self.runtime_store.finish(
                run.run_id,
                RuntimeStatus.REJECTED,
                RuntimeEventName.REJECTED,
                "The public benchmark request or lifecycle evidence was rejected.",
                {
                    "reason_code": str(error),
                    "limitations": [str(error)],
                    "next_action": "correct_public_benchmark_request_or_source",
                },
            )
        except Exception:
            # Deliberately keep implementation internals and any unreviewed
            # source details out of the persisted/public error surface.
            return self.runtime_store.finish(
                run.run_id,
                RuntimeStatus.FAILED,
                RuntimeEventName.FAILED,
                "The local worker stopped before a verified report was available.",
                {
                    "reason_code": "UNEXPECTED_PUBLIC_BENCHMARK_WORKER_FAILURE",
                    "limitations": ["UNEXPECTED_PUBLIC_BENCHMARK_WORKER_FAILURE"],
                    "next_action": "inspect_local_worker_logs_without_exposing_source_data",
                },
            )

    def _finish_mapping_failure(self, run: RuntimeRun, reason_code: str) -> RuntimeRun:
        inconclusive_prefixes = (
            "FRESHRETAILNET_SOURCE_FILE_NOT_FOUND",
            "FRESHRETAILNET_PARQUET_UNREADABLE",
            "PYARROW_REQUIRED_FOR_FRESHRETAILNET_PARQUET",
        )
        if reason_code.startswith(inconclusive_prefixes):
            status = RuntimeStatus.INCONCLUSIVE
            event = RuntimeEventName.INCONCLUSIVE
            detail = "The worker could not obtain sufficient approved public source evidence."
            next_action = "restore_or_validate_configured_public_benchmark_source"
        else:
            status = RuntimeStatus.REJECTED
            event = RuntimeEventName.REJECTED
            detail = "The configured public source did not satisfy the pinned benchmark contract."
            next_action = "correct_public_benchmark_source_or_selection"
        return self.runtime_store.finish(
            run.run_id,
            status,
            event,
            detail,
            {
                "reason_code": reason_code,
                "limitations": [reason_code],
                "next_action": next_action,
            },
        )


def main() -> int:
    """Run one explicit local work item; scheduling remains intentionally absent."""

    parser = argparse.ArgumentParser(description="Run one queued RetailOps public benchmark job.")
    parser.add_argument("--once", action="store_true", help="Process at most one queued job.")
    arguments = parser.parse_args()
    if not arguments.once:
        parser.error("Only --once is supported; scheduling is not enabled in the local runtime.")
    worker = PublicBenchmarkWorker(
        RuntimeStore(settings.runtime_root),
        audit_root=settings.audit_root,
        source_path=settings.public_benchmark_source_path,
        worker_id=os.getenv("RETAILOPS_WORKER_ID"),
    )
    completed = worker.run_once()
    if completed is None:
        print("No queued public benchmark run.")
        return 0
    print(f"{completed.run_id} {completed.status.value}")
    return 0


if __name__ == "__main__":  # pragma: no cover - command-line entry point
    raise SystemExit(main())
