"""Filesystem-backed immutable audit storage for the CSV pilot."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import mkdtemp
from typing import Mapping

from app.schemas.connector import ConnectorRun, SnapshotManifest
from app.schemas.benchmark import FreshRetailNetBenchmarkRun, FreshRetailNetFinalTestReport
from app.schemas.forecast import BaselineRun, ModelLifecycleRun
from app.schemas.foundation import ProductionFoundationAssessment
from app.schemas.pilot import PilotReadinessAssessment
from app.schemas.review import ReviewCase, ReviewDecisionEvent
from app.schemas.workflow import FixtureReviewWorkflowRun


class SnapshotStore:
    """Persist raw connector files and metadata without overwriting a snapshot.

    This is a local-pilot adapter. A production deployment keeps the same
    immutable interface while replacing the filesystem with tenant-isolated
    object and relational storage.
    """

    def __init__(self, root: Path) -> None:
        self.root = root

    @property
    def snapshots_root(self) -> Path:
        return self.root / "snapshots"

    @property
    def runs_root(self) -> Path:
        return self.root / "runs"

    @property
    def baseline_runs_root(self) -> Path:
        return self.root / "baseline-runs"

    @property
    def model_registry_root(self) -> Path:
        return self.root / "model-registry"

    @property
    def pilot_readiness_root(self) -> Path:
        return self.root / "pilot-readiness"

    @property
    def public_benchmark_runs_root(self) -> Path:
        return self.root / "public-benchmark-runs"

    @property
    def public_benchmark_final_test_reports_root(self) -> Path:
        return self.root / "public-benchmark-final-test-reports"

    @property
    def review_cases_root(self) -> Path:
        return self.root / "review-cases"

    @property
    def review_decisions_root(self) -> Path:
        return self.root / "review-decisions"

    @property
    def fixture_review_workflow_runs_root(self) -> Path:
        return self.root / "fixture-review-workflow-runs"

    @property
    def production_foundation_assessments_root(self) -> Path:
        return self.root / "production-foundation-assessments"

    def persist_snapshot(self, manifest: SnapshotManifest, tables: Mapping[str, bytes]) -> Path:
        self.snapshots_root.mkdir(parents=True, exist_ok=True)
        destination = self.snapshots_root / manifest.snapshot_id
        if destination.exists():
            raise FileExistsError(f"Snapshot {manifest.snapshot_id} already exists")

        temporary = Path(mkdtemp(prefix=f".{manifest.snapshot_id}-", dir=self.snapshots_root))
        try:
            for table, payload in tables.items():
                if table in manifest.table_hashes:
                    (temporary / f"{table}.csv").write_bytes(payload)
            (temporary / "manifest.json").write_text(
                json.dumps(manifest.to_dict(), sort_keys=True, indent=2), encoding="utf-8"
            )
            temporary.replace(destination)
        except Exception:
            if temporary.exists():
                for child in temporary.iterdir():
                    child.unlink()
                temporary.rmdir()
            raise
        return destination

    def persist_run(self, run: ConnectorRun) -> Path:
        self.runs_root.mkdir(parents=True, exist_ok=True)
        destination = self.runs_root / f"{run.run_id}.json"
        if destination.exists():
            raise FileExistsError(f"Run {run.run_id} already exists")
        temporary = self.runs_root / f".{run.run_id}.tmp"
        temporary.write_text(json.dumps(run.to_dict(), sort_keys=True, indent=2), encoding="utf-8")
        temporary.replace(destination)
        return destination

    def load_run(self, run_id: str) -> dict[str, object] | None:
        path = self.runs_root / f"{run_id}.json"
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def persist_baseline_run(self, run: BaselineRun) -> Path:
        self.baseline_runs_root.mkdir(parents=True, exist_ok=True)
        destination = self.baseline_runs_root / f"{run.run_id}.json"
        if destination.exists():
            raise FileExistsError(f"Baseline run {run.run_id} already exists")
        temporary = self.baseline_runs_root / f".{run.run_id}.tmp"
        temporary.write_text(json.dumps(run.to_dict(), sort_keys=True, indent=2), encoding="utf-8")
        temporary.replace(destination)
        return destination

    def load_baseline_run(self, run_id: str) -> dict[str, object] | None:
        path = self.baseline_runs_root / f"{run_id}.json"
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def persist_model_run(self, run: ModelLifecycleRun) -> Path:
        """Append one immutable local registry record for a lifecycle evaluation."""

        self.model_registry_root.mkdir(parents=True, exist_ok=True)
        destination = self.model_registry_root / f"{run.model_run_id}.json"
        if destination.exists():
            raise FileExistsError(f"Model run {run.model_run_id} already exists")
        temporary = self.model_registry_root / f".{run.model_run_id}.tmp"
        temporary.write_text(json.dumps(run.to_dict(), sort_keys=True, indent=2), encoding="utf-8")
        temporary.replace(destination)
        return destination

    def load_model_run(self, model_run_id: str) -> dict[str, object] | None:
        path = self.model_registry_root / f"{model_run_id}.json"
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def persist_pilot_readiness(self, assessment: PilotReadinessAssessment) -> Path:
        """Append one immutable, non-secret pilot-readiness assessment."""

        self.pilot_readiness_root.mkdir(parents=True, exist_ok=True)
        destination = self.pilot_readiness_root / f"{assessment.readiness_id}.json"
        if destination.exists():
            raise FileExistsError(f"Pilot readiness {assessment.readiness_id} already exists")
        temporary = self.pilot_readiness_root / f".{assessment.readiness_id}.tmp"
        temporary.write_text(
            json.dumps(assessment.to_dict(), sort_keys=True, indent=2), encoding="utf-8"
        )
        temporary.replace(destination)
        return destination

    def load_pilot_readiness(self, readiness_id: str) -> dict[str, object] | None:
        path = self.pilot_readiness_root / f"{readiness_id}.json"
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def persist_public_benchmark_run(self, run: FreshRetailNetBenchmarkRun) -> Path:
        """Append one immutable public-benchmark provenance and limitation record."""

        self.public_benchmark_runs_root.mkdir(parents=True, exist_ok=True)
        destination = self.public_benchmark_runs_root / f"{run.run_id}.json"
        if destination.exists():
            raise FileExistsError(f"Public benchmark run {run.run_id} already exists")
        temporary = self.public_benchmark_runs_root / f".{run.run_id}.tmp"
        temporary.write_text(json.dumps(run.to_dict(), sort_keys=True, indent=2), encoding="utf-8")
        temporary.replace(destination)
        return destination

    def load_public_benchmark_run(self, run_id: str) -> dict[str, object] | None:
        path = self.public_benchmark_runs_root / f"{run_id}.json"
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def persist_public_benchmark_final_test_report(
        self, report: FreshRetailNetFinalTestReport
    ) -> Path:
        """Persist the single immutable post-selection report for a model run."""

        self.public_benchmark_final_test_reports_root.mkdir(parents=True, exist_ok=True)
        destination = self.public_benchmark_final_test_reports_root / f"{report.report_id}.json"
        if destination.exists():
            raise FileExistsError(f"Final test report {report.report_id} already exists")
        temporary = self.public_benchmark_final_test_reports_root / f".{report.report_id}.tmp"
        temporary.write_text(json.dumps(report.to_dict(), sort_keys=True, indent=2), encoding="utf-8")
        temporary.replace(destination)
        return destination

    def load_public_benchmark_final_test_report(self, report_id: str) -> dict[str, object] | None:
        path = self.public_benchmark_final_test_reports_root / f"{report_id}.json"
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def persist_review_case(self, case: ReviewCase) -> Path:
        """Append one fixture-only review case without mutating a draft or critic result."""

        self.review_cases_root.mkdir(parents=True, exist_ok=True)
        destination = self.review_cases_root / f"{case.case_id}.json"
        if destination.exists():
            raise FileExistsError(f"Review case {case.case_id} already exists")
        temporary = self.review_cases_root / f".{case.case_id}.tmp"
        temporary.write_text(json.dumps(case.to_dict(), sort_keys=True, indent=2), encoding="utf-8")
        temporary.replace(destination)
        return destination

    def load_review_case(self, case_id: str) -> dict[str, object] | None:
        path = self.review_cases_root / f"{case_id}.json"
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def list_review_cases(self) -> list[dict[str, object]]:
        if not self.review_cases_root.exists():
            return []
        return [
            json.loads(path.read_text(encoding="utf-8"))
            for path in sorted(self.review_cases_root.glob("*.json"))
        ]

    def persist_review_decision(self, decision: ReviewDecisionEvent) -> Path:
        """Append an immutable human-review event; it never executes the draft."""

        self.review_decisions_root.mkdir(parents=True, exist_ok=True)
        destination = self.review_decisions_root / f"{decision.decision_id}.json"
        if destination.exists():
            raise FileExistsError(f"Review decision {decision.decision_id} already exists")
        temporary = self.review_decisions_root / f".{decision.decision_id}.tmp"
        temporary.write_text(json.dumps(decision.to_dict(), sort_keys=True, indent=2), encoding="utf-8")
        temporary.replace(destination)
        return destination

    def list_review_decisions(self, case_id: str) -> list[dict[str, object]]:
        if not self.review_decisions_root.exists():
            return []
        decisions: list[dict[str, object]] = []
        for path in sorted(self.review_decisions_root.glob("*.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            if payload.get("case_id") == case_id:
                decisions.append(payload)
        return sorted(
            decisions,
            key=lambda payload: (str(payload.get("recorded_at", "")), str(payload.get("decision_id", ""))),
        )

    def persist_fixture_review_workflow_run(self, run: FixtureReviewWorkflowRun) -> Path:
        """Append an immutable local event stream for a fixture-only review workflow."""

        self.fixture_review_workflow_runs_root.mkdir(parents=True, exist_ok=True)
        destination = self.fixture_review_workflow_runs_root / f"{run.workflow_run_id}.json"
        if destination.exists():
            raise FileExistsError(f"Fixture review workflow {run.workflow_run_id} already exists")
        temporary = self.fixture_review_workflow_runs_root / f".{run.workflow_run_id}.tmp"
        temporary.write_text(json.dumps(run.to_dict(), sort_keys=True, indent=2), encoding="utf-8")
        temporary.replace(destination)
        return destination

    def load_fixture_review_workflow_run(self, workflow_run_id: str) -> dict[str, object] | None:
        path = self.fixture_review_workflow_runs_root / f"{workflow_run_id}.json"
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def persist_production_foundation_assessment(
        self, assessment: ProductionFoundationAssessment
    ) -> Path:
        """Persist a non-secret, provisioning-only P0 assessment without overwriting it."""

        self.production_foundation_assessments_root.mkdir(parents=True, exist_ok=True)
        destination = self.production_foundation_assessments_root / f"{assessment.assessment_id}.json"
        if destination.exists():
            raise FileExistsError(
                f"Production foundation assessment {assessment.assessment_id} already exists"
            )
        temporary = self.production_foundation_assessments_root / f".{assessment.assessment_id}.tmp"
        temporary.write_text(
            json.dumps(assessment.to_dict(), sort_keys=True, indent=2), encoding="utf-8"
        )
        temporary.replace(destination)
        return destination

    def load_production_foundation_assessment(
        self, assessment_id: str
    ) -> dict[str, object] | None:
        path = self.production_foundation_assessments_root / f"{assessment_id}.json"
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))
